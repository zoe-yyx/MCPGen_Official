"""
tasks/q3_incremental_evolution.py

Q3: Incremental Evolution Evaluation
------------------------------------

Goal:
Given 100 MCP projects, each with a *baseline* `workflow_simple.json` and a ground-truth full `workflow.json`,
ask an LLM to evolve the baseline into a complete workflow **with minimal augmentation** while preserving all
previously satisfied behaviors. The LLM must also generate a `run_workflow.py` that **actually** uses MCP tools.

We then evaluate:
- Subgraph Preservation Rate (edge- and path2-level)
- Structural deltas (ΔV, ΔE) and ratios
- Minimality vs theoretical minimal deltas (from baseline to gold)
- GED approximation between candidate and gold (nodes+edges mismatches)
- Static check that run_workflow.py calls MCP tools (heuristic)
- Produce per-project JSON & Markdown, plus an aggregate summary.
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import re
import sys
import time
from asyncio.subprocess import PIPE
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from shutil import which

# Optional imports (if present in the repo)
from core.config import EvaluationConfig  # type: ignore
from utils.llm_interface import LLMInterface  # type: ignore

from utils.incremental_workflow import (
    collect_projects,
    try_find_file,
    load_json,
    extract_graph,
    compute_preservation,
    compute_deltas,
    compute_minimality,
    compute_tool_chain_accuracy,
    approximate_ged_nodes_edges,
    inspect_mcp_usage,
)
from utils.baseline_generator import ensure_baseline
from utils.isolated_test_env import IsolatedTestEnvironment

Q3_BASELINE_CANDIDATES = ["workflow_simple.json", "workflow_simple_random.json",
                          "workflow_simple_r*.json", "workflow_simple_r*_random.json"]
Q3_GOLD_CANDIDATES = ["workflow.json", "workflow_full.json"]
Q3_OUTPUT_DIRNAME = "generated"  # avoid clobbering user's canonical files


# ---------------------------
# Utilities
# ---------------------------

def _strip_code_fences(text: str) -> str:
    """
    Remove Markdown code fences (```json, ```python, etc.) from LLM output.
    Returns original text if no fences are found.
    """
    txt = text.strip()
    m = re.search(r"```(?:\w+)?\s*\n(.*?)\n\s*```", txt, re.S)
    if m:
        return m.group(1).strip()
    # Fallback for odd cases like only opening or trailing ```
    if txt.startswith("```"):
        txt = re.sub(r"^```[^\n]*\n", "", txt)
        txt = re.sub(r"\n```$", "", txt)
    return txt.strip()


_IMPORT_PKG_MAP: Dict[str, str] = {
    "jinja2": "jinja2",
    "fastmcp": "fastmcp",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    # "requests": "requests",
    # "pandas": "pandas",
    # "pydantic": "pydantic",
}

def _parse_import_modules(code: str) -> List[str]:
    mods = set()
    for m in re.finditer(r'^\s*import\s+([a-zA-Z0-9_]+)', code, re.M):
        mods.add(m.group(1))
    for m in re.finditer(r'^\s*from\s+([a-zA-Z0-9_]+)\s+import\s+', code, re.M):
        mods.add(m.group(1))
    return sorted(mods)


def _extract_tool_schemas(project_dir: Path) -> str:
    """
    Read ``mcp_server/server.py`` and extract all MCP-tool-registered function
    names and their signatures to inject into the LLM prompt.

    Covers four registration patterns:
      1. ``@mcp.tool()`` decorator on function/async function definitions
      2. ``mcp.tool()(func_name)`` — call-style registration (simple name)
      3. ``mcp.tool()(obj.method)`` — call-style with dotted access
      4. ``mcp.tool()(wrapper(func))`` — call-style with wrapper
      5. ``setup_xxx_tools(mcp)`` — follow import into sub-module and find
         ``@mcp.tool()`` decorated functions there

    Returns a human-readable listing, or an empty string if extraction fails.
    """
    import ast as _ast

    server_py = project_dir / "mcp_server" / "server.py"
    if not server_py.exists():
        return ""

    try:
        source = server_py.read_text(encoding="utf-8")
        tree = _ast.parse(source)
    except Exception:
        return ""

    # Helper: check if an AST node is a call to mcp.tool()
    def _is_mcp_tool_call(node: _ast.AST) -> bool:
        """Return True if *node* is ``mcp.tool()(...)``."""
        if not isinstance(node, _ast.Call):
            return False
        func = node.func
        if isinstance(func, _ast.Call):
            inner = func.func
            if isinstance(inner, _ast.Attribute) and inner.attr == "tool":
                return True
        return False

    def _is_mcp_tool_decorator(dec: _ast.AST) -> bool:
        """Return True if *dec* is ``@mcp.tool()`` or ``@mcp.tool``."""
        if isinstance(dec, _ast.Call):
            f = dec.func
            if isinstance(f, _ast.Attribute) and f.attr == "tool":
                return True
        elif isinstance(dec, _ast.Attribute) and dec.attr == "tool":
            return True
        return False

    def _format_funcdef(node: _ast.AST) -> str:
        """Format a FunctionDef/AsyncFunctionDef into ``name(args)  # doc``."""
        args = []
        for arg in node.args.args:
            if arg.arg in ("self", "ctx"):
                continue
            ann = ""
            if arg.annotation:
                try:
                    ann = _ast.unparse(arg.annotation)
                except Exception:
                    pass
            args.append(f"{arg.arg}: {ann}" if ann else arg.arg)
        sig = f"{node.name}({', '.join(args)})"
        docstring = _ast.get_docstring(node) or ""
        if docstring:
            docstring = docstring.strip().split("\n")[0]
        return f"  - {sig}  # {docstring}" if docstring else f"  - {sig}"

    def _resolve_funcdef(name: str, tree: _ast.Module) -> Optional[_ast.AST]:
        """Find FunctionDef/AsyncFunctionDef with given *name* in *tree*."""
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name == name:
                return node
        return None

    tools: List[str] = []
    seen_names: set = set()

    # --- Pattern 1: @mcp.tool() decorated functions ---
    for node in _ast.walk(tree):
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if _is_mcp_tool_decorator(dec):
                if node.name not in seen_names:
                    seen_names.add(node.name)
                    tools.append(_format_funcdef(node))
                break

    # --- Patterns 2-4: mcp.tool()(expr) call-style registration ---
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Expr):
            continue
        call = node.value
        if not _is_mcp_tool_call(call):
            continue
        if not call.args:
            continue
        arg = call.args[0]
        tool_name = None
        # Pattern 2: mcp.tool()(func_name) — simple Name
        if isinstance(arg, _ast.Name):
            tool_name = arg.id
        # Pattern 3: mcp.tool()(obj.method) — Attribute
        elif isinstance(arg, _ast.Attribute):
            tool_name = arg.attr
        # Pattern 4: mcp.tool()(wrapper(func)) — Call wrapping a Name/Attribute
        elif isinstance(arg, _ast.Call) and arg.args:
            inner = arg.args[0]
            if isinstance(inner, _ast.Name):
                tool_name = inner.id
            elif isinstance(inner, _ast.Attribute):
                tool_name = inner.attr

        if tool_name and tool_name not in seen_names:
            seen_names.add(tool_name)
            # Try to find function definition for signature
            funcdef = _resolve_funcdef(tool_name, tree)
            if funcdef:
                tools.append(_format_funcdef(funcdef))
            else:
                tools.append(f"  - {tool_name}()")

    # --- Pattern 5: setup_xxx_tools(mcp) — follow into sub-module ---
    setup_calls: List[str] = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Expr):
            continue
        call = node.value
        if not isinstance(call, _ast.Call):
            continue
        # Match setup_xxx_tools(mcp) or setup_xxx_tools(mcp, ...)
        func_node = call.func
        func_name = None
        if isinstance(func_node, _ast.Name):
            func_name = func_node.id
        elif isinstance(func_node, _ast.Attribute):
            func_name = func_node.attr
        if func_name and re.match(r"setup_\w+_tools$", func_name):
            setup_calls.append(func_name)

    if setup_calls:
        # Resolve imports to find which module each setup function comes from
        import_map: Dict[str, str] = {}
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ImportFrom) and node.module:
                for alias in node.names:
                    real_name = alias.asname or alias.name
                    import_map[real_name] = node.module

        for setup_fn in setup_calls:
            mod_path_str = import_map.get(setup_fn, "")
            if not mod_path_str:
                continue
            # Convert dotted module path to file path relative to project_dir
            rel = mod_path_str.replace(".", "/") + ".py"
            candidates = [
                project_dir / rel,
                project_dir / "mcp_server" / rel,
            ]
            # Also try stripping leading "mcp_server." prefix
            if mod_path_str.startswith("mcp_server."):
                stripped = mod_path_str[len("mcp_server."):].replace(".", "/") + ".py"
                candidates.append(project_dir / "mcp_server" / stripped)

            sub_source = None
            for cand in candidates:
                if cand.exists():
                    try:
                        sub_source = cand.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    break

            if not sub_source:
                continue

            try:
                sub_tree = _ast.parse(sub_source)
            except Exception:
                continue

            # Find @mcp.tool() decorated functions inside the setup function
            # or at module level
            for sub_node in _ast.walk(sub_tree):
                if not isinstance(sub_node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    continue
                for dec in sub_node.decorator_list:
                    if _is_mcp_tool_decorator(dec):
                        if sub_node.name not in seen_names:
                            seen_names.add(sub_node.name)
                            tools.append(_format_funcdef(sub_node))
                        break

    if not tools:
        return ""
    return "Available MCP tools (from server.py):\n" + "\n".join(tools)


# ---------------------------
# Prompts
# ---------------------------

Q3_WORKFLOW_PROMPT = """You are given a baseline MCP workflow (a strict subset of the full workflow) and the tools
available in the MCP server at `mcp_server/server.py`. **Evolve** the baseline into the full workflow while:
1) Preserving all behaviors that already succeed (backward compatibility).
2) Adding the **minimal** steps/edges to satisfy the complete requirements described in the project README.
3) Keeping existing step_ids and subgraphs intact whenever possible (subgraph preservation).
4) Using MCP tool names and parameter schemas exactly as exposed by the server.

Output ONLY a JSON object for `workflow.json` in this schema:
{
  "workflow": { ... arbitrary metadata ... },
  "configuration": { ... environment_variables etc. ... },
  "workflow_steps": [
    {
      "step_id": "1",
      "name": "...",
      "type": "initialization|processing|validation|output",
      "description": "...",
      "mcp_tool": "<tool name>",
      "parameters": { "input": { ... tool arguments ... } },
      "conditions": { "execute_if": "<expr, optional>" },
      "next_steps": ["2","5"]
    },
    ...
  ]
}

When passing data between steps, use templating like {{ step_3.output }} or {{ step_3.some_field }}.
Avoid inventing tools that the MCP server does not expose.
"""

Q3_RUNNER_PROMPT = """Generate a Python file `run_workflow.py` that executes the evolved workflow using the MCP server.
**Requirements**:
- Connect via `async with Client("mcp_server/server.py") as client:` (fastmcp or equivalent).
- Load the colocated `workflow.json` and iterate over `workflow_steps`, following `next_steps`.
- Resolve templating refs (e.g., {{ step_3.xxx }}, {{ env.VAR }}, {{ workflow.* }}) from prior results and environment.
- Actually call MCP tools (e.g., `await client.list_tools()`, then `await client.call_tool(tool_name, args)`).
- Log to `logs/workflow.log` and write artifacts to `results/outputs/` when present.
- Output ONLY the Python source code.
"""


# ---------------------------
# Dataclasses
# ---------------------------

@dataclass
class ProjectResult:
    project: str
    metrics: Dict[str, Any]
    files: Dict[str, str]  # relative output paths for generated files

    def to_json(self) -> Dict[str, Any]:
        return {"project": self.project, "metrics": self.metrics, "files": self.files}


def _collect_q3_projects(projects_root: Path) -> List[Path]:
    """
    Collect project directories that have *either* a baseline ``workflow_simple*.json``
    or a gold ``workflow.json`` (from which a baseline can be auto-generated).
    """
    projects = []
    for p in sorted(projects_root.iterdir()):
        if not p.is_dir():
            continue
        has_baseline = any(p.glob("workflow_simple*.json"))
        has_gold = any((p / g).exists() for g in Q3_GOLD_CANDIDATES)
        if has_baseline or has_gold:
            projects.append(p)
    return projects


# ---------------------------
# Core evaluation logic
# ---------------------------

class Q3Evaluator:
    def __init__(self, cfg: EvaluationConfig, llm: Optional[LLMInterface] = None, do_exec: bool = False):
        self.cfg = cfg
        self.llm = llm or LLMInterface(cfg.llm_config)
        self.do_exec = do_exec  # whether to actually execute generated/run_workflow.py

    async def _llm_generate_workflow(
        self,
        baseline: Dict[str, Any],
        readme_text: str,
        tool_schema_text: str = "",
    ) -> Dict[str, Any]:
        prompt = Q3_WORKFLOW_PROMPT
        if tool_schema_text:
            prompt += "\n\n" + tool_schema_text
        prompt += (
            "\n\nREADME:\n" + readme_text
            + "\n\nBASELINE workflow_simple.json:\n"
            + json.dumps(baseline, ensure_ascii=False, indent=2)
        )

        text = await self.llm.generate_response(
            prompt=prompt,
            system_message=getattr(self.cfg, "system_prompt", "You are a helpful assistant."),
            temperature=getattr(self.cfg, "temperature", 0.2),
            max_tokens=getattr(self.cfg.llm_config, "max_tokens", 16000),
        )

        # Strip code fences (```json ... ```) if present
        cleaned = _strip_code_fences(text)

        try:
            return json.loads(cleaned)
        except Exception as e:
            # Fallback 1: extract JSON block from mixed content
            match = re.search(r"\{.*\}", cleaned, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            # Fallback 2: truncated JSON — close unbalanced brackets and retry
            stack, in_str, esc, start = [], False, False, None
            for i, ch in enumerate(cleaned):
                if ch == '{' and not in_str and start is None:
                    start = i
                if start is None:
                    continue
                if in_str:
                    if esc: esc = False
                    elif ch == '\\': esc = True
                    elif ch == '"': in_str = False
                else:
                    if ch == '"': in_str = True
                    elif ch == '{': stack.append(ch)
                    elif ch == '[': stack.append(ch)
                    elif ch == '}':
                        if stack and stack[-1] == '{': stack.pop()
                    elif ch == ']':
                        if stack and stack[-1] == '[': stack.pop()
            if start is not None:
                payload = cleaned[start:]
                while stack:
                    payload += '}' if stack.pop() == '{' else ']'
                payload = re.sub(r',(\s*[}\]])', r'\1', payload)
                try:
                    return json.loads(payload)
                except Exception:
                    pass
            raise RuntimeError(
                f"Failed to parse LLM workflow JSON: {e}\n---RAW---\n{text}"
            )

    async def _llm_generate_runner(
        self,
        project_dir: Path,
        evolved_workflow: Dict[str, Any],
        tool_schema_text: str = "",
    ) -> str:
        prompt = Q3_RUNNER_PROMPT
        if tool_schema_text:
            prompt += "\n\n" + tool_schema_text
        prompt += (
            "\n\nEvolved workflow.json:\n"
            + json.dumps(evolved_workflow, ensure_ascii=False, indent=2)
        )

        code = await self.llm.generate_response(
            prompt=prompt,
            system_message=getattr(self.cfg, "system_prompt", "You are a helpful assistant."),
            temperature=getattr(self.cfg, "temperature", 0.2),
            max_tokens=getattr(self.cfg.llm_config, "max_tokens", 16000),
        )
        # strip possible ```python fences before saving
        code = _strip_code_fences(code)
        return code

    async def _ensure_runtime_deps(self, project_dir: Path, runner_code: str) -> None:
        """
        """
        if not which("uv"):
            return

        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        env.pop("CONDA_PREFIX", None)

        sync_cmd = ["uv", "sync", "--frozen", "-q"] if (project_dir / "uv.lock").exists() else ["uv", "sync", "-q"]
        proc_sync = await asyncio.create_subprocess_exec(
            *sync_cmd, cwd=str(project_dir), env=env, stdout=PIPE, stderr=PIPE
        )
        await proc_sync.communicate()

        modules = _parse_import_modules(runner_code)
        if not modules:
            return

        missing_pkgs: List[str] = []
        for mod in modules:
            pkg = _IMPORT_PKG_MAP.get(mod)
            if not pkg:
                continue
            chk = await asyncio.create_subprocess_exec(
                "uv", "run", "python", "-c", f"import {mod}",
                cwd=str(project_dir), env=env, stdout=PIPE, stderr=PIPE
            )
            await chk.communicate()
            if chk.returncode != 0:
                missing_pkgs.append(pkg)

        if missing_pkgs:
            pip = await asyncio.create_subprocess_exec(
                "uv", "run", "python", "-m", "pip", "install", "-q", *missing_pkgs,
                cwd=str(project_dir), env=env, stdout=PIPE, stderr=PIPE
            )
            await pip.communicate()

    def _exec_via_isolated_env(
        self,
        project_dir: Path,
        evolved_workflow: Dict[str, Any],
        runner_code: str,
        timeout_sec: float = 120.0,
    ) -> Dict[str, Any]:
        """
        Execute the generated workflow + runner inside an IsolatedTestEnvironment.

        Steps:
        1. Create an isolated copy of the project.
        2. Overwrite ``workflow.json`` and ``run_workflow.py`` with the LLM output.
        3. Run via ``IsolatedTestEnvironment.run_workflow_test()``.
        """
        try:
            with IsolatedTestEnvironment(project_dir) as env:
                iso_dir = env.get_test_workflow_dir()

                # Overwrite workflow.json with the evolved version
                (iso_dir / "workflow.json").write_text(
                    json.dumps(evolved_workflow, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                # Overwrite run_workflow.py with the generated runner
                (iso_dir / "run_workflow.py").write_text(runner_code, encoding="utf-8")

                result = env.run_workflow_test(timeout=timeout_sec)

            # Trim large fields for the metrics JSON
            trimmed: Dict[str, Any] = {
                "executed": True,
                "success": result.get("success", False),
                "exit_code": result.get("returncode", -1),
                "execution_time": result.get("execution_time", 0),
                "error": result.get("error"),
                "command": result.get("command"),
            }
            # Persist stdout/stderr alongside existing outputs
            out_dir = project_dir / "results" / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)
            if result.get("stdout"):
                (out_dir / "runner_stdout.txt").write_text(result["stdout"], encoding="utf-8")
                trimmed["stdout_file"] = "results/outputs/runner_stdout.txt"
            if result.get("stderr"):
                (out_dir / "runner_stderr.txt").write_text(result["stderr"], encoding="utf-8")
                trimmed["stderr_file"] = "results/outputs/runner_stderr.txt"

            return trimmed
        except Exception as e:
            return {"executed": False, "success": False, "error": str(e)}

    async def evaluate_project(self, project_dir: Path, central_out_dir: Optional[Path] = None) -> ProjectResult:
        # 0) Auto-generate baseline if missing
        baseline_ratio = getattr(self.cfg, "baseline_ratio", 0.5)
        baseline_mode = getattr(self.cfg, "baseline_mode", "prefix")
        baseline_seed = getattr(self.cfg, "baseline_seed", None)
        baseline_path = ensure_baseline(
            project_dir,
            baseline_name="workflow_simple.json",
            gold_candidates=Q3_GOLD_CANDIDATES,
            ratio=baseline_ratio,
            mode=baseline_mode,
            seed=baseline_seed,
        )

        # 1) Locate gold workflow
        gold_path = try_find_file(project_dir, Q3_GOLD_CANDIDATES)
        if not gold_path:
            raise FileNotFoundError(f"No gold workflow.json found in {project_dir}")
        readme_path = try_find_file(project_dir, ["README.md", "readme.md", "Readme.md"])

        # 2) Load artifacts
        baseline = load_json(baseline_path)
        gold = load_json(gold_path)
        readme_text = readme_path.read_text(encoding="utf-8") if readme_path else ""

        # 2.1) Extract tool schemas from server.py for prompt injection
        tool_schema_text = _extract_tool_schemas(project_dir)

        # 3) Ask the LLM to produce evolved workflow + runner
        evolved = await self._llm_generate_workflow(baseline, readme_text, tool_schema_text)
        runner_code = await self._llm_generate_runner(project_dir, evolved, tool_schema_text)

        # 4) Save generated artifacts under project/generated/
        out_dir = project_dir / Q3_OUTPUT_DIRNAME
        out_dir.mkdir(exist_ok=True, parents=True)
        evolved_path = out_dir / "workflow.json"
        runner_path = out_dir / "run_workflow.py"
        evolved_path.write_text(json.dumps(evolved, ensure_ascii=False, indent=2), encoding="utf-8")
        runner_path.write_text(runner_code, encoding="utf-8")

        # 4.5) E2E execution via IsolatedTestEnvironment
        runtime = None
        if self.do_exec:
            runtime = self._exec_via_isolated_env(project_dir, evolved, runner_code)

        # 5) Compute graphs & metrics
        W_simple = extract_graph(baseline)
        W_gold = extract_graph(gold)
        W_prime = extract_graph(evolved)

        spr = compute_preservation(W_simple, W_prime)
        deltas = compute_deltas(W_simple, W_prime)
        minimality = compute_minimality(W_simple, W_gold, W_prime)
        ged = approximate_ged_nodes_edges(W_prime, W_gold)
        tool_chain = compute_tool_chain_accuracy(W_prime, W_gold)

        ok_mcp, confidence, flags = inspect_mcp_usage(runner_code)

        metrics = {
            "spr": asdict(spr),
            "deltas": asdict(deltas),
            "minimality": asdict(minimality),
            "ged_nodes_edges": ged,
            "tool_chain": asdict(tool_chain),
            "mcp_call_detected": ok_mcp,
            "mcp_call_confidence": confidence,
            "mcp_call_flags": flags,
        }
        if runtime is not None:
            metrics["runtime"] = runtime

        # 6) Persist metrics
        metrics_dir = project_dir / "results" / "metrics"
        metrics_dir.mkdir(exist_ok=True, parents=True)
        (metrics_dir / "q3_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

        # 7) Also save to central output directory for easy access
        if central_out_dir:
            proj_out_dir = central_out_dir / "projects" / project_dir.name
            proj_out_dir.mkdir(exist_ok=True, parents=True)
            (proj_out_dir / "workflow.json").write_text(json.dumps(evolved, ensure_ascii=False, indent=2), encoding="utf-8")
            (proj_out_dir / "run_workflow.py").write_text(runner_code, encoding="utf-8")
            (proj_out_dir / "q3_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            # Preserve runner stderr per-model so it isn't overwritten by other models running the same project
            src_stderr = project_dir / "results" / "outputs" / "runner_stderr.txt"
            if src_stderr.exists():
                try:
                    (proj_out_dir / "runner_stderr.txt").write_text(src_stderr.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                except Exception:
                    pass
            src_stdout = project_dir / "results" / "outputs" / "runner_stdout.txt"
            if src_stdout.exists():
                try:
                    (proj_out_dir / "runner_stdout.txt").write_text(src_stdout.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                except Exception:
                    pass

        return ProjectResult(project=project_dir.name, metrics=metrics, files={
            "evolved_workflow": str(evolved_path.relative_to(project_dir)),
            "runner": str(runner_path.relative_to(project_dir)),
            "metrics": str((metrics_dir / "q3_metrics.json").relative_to(project_dir)),
        })

    async def run_all(self) -> Dict[str, Any]:
        projects_root = Path(getattr(self.cfg, "projects_root", "mcp_projects"))
        output_root = Path(getattr(self.cfg, "out_dir", "results"))

        model_name = getattr(self.cfg.llm_config, "model_name", "unknown_model")
        baseline_ratio = getattr(self.cfg, "baseline_ratio", 0.5)
        baseline_mode = getattr(self.cfg, "baseline_mode", "prefix")
        ratio_tag = f"r{baseline_ratio:.2f}".replace(".", "")  # 0.5 -> "r050"
        if baseline_mode == "random":
            ratio_tag += "_random"
        out_dir = output_root / "q3_incremental_evolution" / model_name / ratio_tag
        out_dir.mkdir(exist_ok=True, parents=True)

        projects = _collect_q3_projects(projects_root)
        if getattr(self.cfg, "limit_projects", 0) > 0:
            projects = projects[: self.cfg.limit_projects]

        per_project: List[ProjectResult] = []
        skipped = 0
        for p in projects:
            # Resume: skip projects that already have successful results
            proj_metrics_path = out_dir / "projects" / p.name / "q3_metrics.json"
            if proj_metrics_path.exists():
                try:
                    existing_metrics = json.loads(proj_metrics_path.read_text(encoding="utf-8"))
                    per_project.append(ProjectResult(
                        project=p.name, metrics=existing_metrics, files={}
                    ))
                    skipped += 1
                    continue
                except Exception:
                    pass  # corrupted file, re-evaluate

            # Remove stale failure record if retrying
            fail_file = out_dir / "q3_failures" / f"{p.name}.error.txt"
            if fail_file.exists():
                fail_file.unlink()

            try:
                res = await self.evaluate_project(p, central_out_dir=out_dir)
                per_project.append(res)
            except Exception as e:
                # Write a failure record to facilitate debugging
                fail_dir = out_dir / "q3_failures"
                fail_dir.mkdir(exist_ok=True, parents=True)
                (fail_dir / f"{p.name}.error.txt").write_text(str(e), encoding="utf-8")

        if skipped:
            print(f"[Resume] Skipped {skipped} already-succeeded projects, evaluating {len(projects) - skipped} remaining.")

        # Aggregate summary
        total = len(projects)
        n_eval = max(1, len(per_project))
        ok_mcp = sum(1 for r in per_project if r.metrics.get("mcp_call_detected"))

        # Existing structural metrics
        avg_spr_edge = _avg([r.metrics["spr"]["edge_preservation_rate"] for r in per_project])
        avg_ged = _avg([r.metrics["ged_nodes_edges"] for r in per_project])
        avg_min_node = _avg([r.metrics["minimality"]["node_ratio_vs_min"] for r in per_project])
        avg_min_edge = _avg([r.metrics["minimality"]["edge_ratio_vs_min"] for r in per_project])

        # New semantic metrics
        avg_tool_chain_acc = _avg([r.metrics["tool_chain"]["tool_name_accuracy"] for r in per_project])
        avg_data_ref_acc = _avg([r.metrics["tool_chain"]["data_ref_accuracy"] for r in per_project])
        avg_node_content_f1 = _avg([r.metrics["minimality"]["node_content_f1"] for r in per_project])

        # E2E success rate (only among projects where execution was attempted)
        exec_projects = [r for r in per_project if r.metrics.get("runtime") and r.metrics["runtime"].get("executed")]
        e2e_success_rate = (
            sum(1 for r in exec_projects if r.metrics["runtime"].get("success")) / max(1, len(exec_projects))
            if exec_projects else None
        )

        summary = {
            "total_projects": total,
            "evaluated": len(per_project),
            "e2e_success_rate": e2e_success_rate,
            "avg_tool_chain_accuracy": avg_tool_chain_acc,
            "avg_data_ref_accuracy": avg_data_ref_acc,
            "mcp_call_detected_rate": (ok_mcp / n_eval),
            "avg_edge_SPR": avg_spr_edge,
            "avg_ged_nodes_edges": avg_ged,
            "avg_minimality_node_ratio": avg_min_node,
            "avg_minimality_edge_ratio": avg_min_edge,
            "avg_node_content_f1": avg_node_content_f1,
            "projects": [r.to_json() for r in per_project],
        }

        # Save
        (out_dir / "q3_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary


def _avg(xs: List[float]) -> float:
    if not xs:
        return 0.0
    return float(sum(xs) / len(xs))


# ---------------------------
# CLI
# ---------------------------

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--exec",
        dest="do_exec",
        action="store_true",
        help="Actually execute generated/run_workflow.py via IsolatedTestEnvironment"
    )
    parser.add_argument(
        "--baseline-ratio",
        type=float,
        default=0.5,
        help="Fraction of workflow steps to keep in auto-generated baseline (default 0.5)"
    )
    parser.add_argument(
        "--baseline-mode",
        choices=["prefix", "random"],
        default="prefix",
        help="Baseline generation mode: 'prefix' keeps the first N steps, "
             "'random' randomly samples N steps (default: prefix)"
    )
    parser.add_argument(
        "--baseline-seed",
        type=int,
        default=None,
        help="Random seed for reproducibility when --baseline-mode=random"
    )
    args = parser.parse_args()

    cfg = EvaluationConfig(args.config)
    cfg.projects_root = args.dataset
    cfg.out_dir = args.output
    cfg.baseline_ratio = args.baseline_ratio
    cfg.baseline_mode = args.baseline_mode
    cfg.baseline_seed = args.baseline_seed

    ev = Q3Evaluator(cfg=cfg, do_exec=args.do_exec)
    summary = await ev.run_all()

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
