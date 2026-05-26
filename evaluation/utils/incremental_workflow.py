"""
utils/q3_utils.py

Utilities for Q3 evaluation that work with the user's workflow.json schema:
{
  "workflow": {...},
  "configuration": {...},
  "workflow_steps": [ { ... } ]
}

Backwards-compatibility: also supports legacy {"steps":[...]} structures.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------
# I/O helpers
# ---------------------------

def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def try_find_file(dir_path: Path, candidates: List[str]) -> Optional[Path]:
    for name in candidates:
        p = dir_path / name
        if p.exists():
            return p
    return None


def collect_projects(projects_root: Path) -> List[Path]:
    """
    A project is any directory containing a baseline workflow_simple.json (or workflow.simple.json).
    """
    projects = []
    for p in projects_root.glob("*"):
        if p.is_dir():
            if (p / "workflow_simple.json").exists() or (p / "workflow.simple.json").exists():
                projects.append(p)
    return sorted(projects)


# ---------------------------
# Graph model
# ---------------------------

@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str = "next"  # "next", "else", "error"

    def as_tuple(self) -> Tuple[str, str, str]:
        return (self.src, self.dst, self.kind)


@dataclass
class GraphView:
    nodes: Set[str]
    edges: List[Edge]              # directional edges
    data_refs: Dict[str, Set[str]] # step_id -> {referenced producer step_ids}
    node_attrs: Dict[str, Dict[str, Any]] = None  # step_id -> {mcp_tool, parameters, ...}

    def __post_init__(self):
        if self.node_attrs is None:
            self.node_attrs = {}

    def edge_set(self) -> Set[Tuple[str, str, str]]:
        return {e.as_tuple() for e in self.edges}


def _normalize_step_id(s: Any) -> str:
    return str(s).strip()


# ---------------------------
# Extraction for new schema (and legacy fallback)
# ---------------------------

def extract_graph(workflow: Dict[str, Any]) -> GraphView:
    """
    Accept both the user's schema with "workflow_steps" and a legacy {"steps":[...]} layout.

    Step fields we look at:
      - step_id (string)
      - next_steps (list[str])
      - else_steps (legacy, optional)
      - error_handler (legacy, optional: str | {"goto": "..."})
      - parameters: we dive into parameters.input to mine templated references
      - conditions.execute_if: may include templated refs as well

    Data refs are detected from templating patterns like:
      {{ step_3.parsed_data }}, {{ step_X.output.foo }}
    We ignore {{ env.* }} and {{ workflow.* }} for data dependencies.
    """
    steps: List[Dict[str, Any]] = workflow.get("workflow_steps") or workflow.get("steps") or []
    nodes: Set[str] = set()
    edges: List[Edge] = []
    data_refs: Dict[str, Set[str]] = {}
    node_attrs: Dict[str, Dict[str, Any]] = {}

    for step in steps:
        sid = _normalize_step_id(step.get("step_id", ""))
        if not sid:
            continue
        nodes.add(sid)

        # Save node attributes (normalize mcp_tool to str)
        raw_tool = step.get("mcp_tool", "")
        if isinstance(raw_tool, list):
            raw_tool = raw_tool[0] if raw_tool else ""
        node_attrs[sid] = {
            "mcp_tool": str(raw_tool),
            "parameters": step.get("parameters", {}),
        }

        # Control edges
        for dst in (step.get("next_steps") or []):
            if dst:
                edges.append(Edge(sid, _normalize_step_id(dst), "next"))

        for dst in (step.get("else_steps") or []):
            if dst:
                edges.append(Edge(sid, _normalize_step_id(dst), "else"))

        err = step.get("error_handler")
        if isinstance(err, str) and err:
            edges.append(Edge(sid, _normalize_step_id(err), "error"))
        elif isinstance(err, dict):
            maybe = err.get("goto") or err.get("step")
            if maybe:
                edges.append(Edge(sid, _normalize_step_id(maybe), "error"))

        # Data refs: parameters.input and conditions.execute_if
        refs: Set[str] = set()
        params = step.get("parameters", {})
        if isinstance(params, dict):
            refs |= find_step_references(params.get("input", params))
        conds = step.get("conditions", {})
        if isinstance(conds, dict):
            refs |= find_step_references(conds.get("execute_if", ""))
        if refs:
            data_refs[sid] = refs

    return GraphView(nodes, edges, data_refs, node_attrs)


# ---------------------------
# Reference extraction
# ---------------------------

# General pattern: {{ head.tail }}
#   head ∈ { step_3, step_alpha, env, workflow, 3, alpha }
# We only keep step references; env/workflow are ignored as deps.
_STEP_REF_GENERAL_RE = re.compile(r"\{\{\s*([A-Za-z0-9_\-]+)\.([A-Za-z0-9_\-\.]+)\s*\}\}")

def find_step_references(val: Any) -> Set[str]:
    """
    Extract producer step_ids referenced by templating:
      {{ step_3.parsed_data }}, {{ step_X.output.foo }}, {{ 3.output }}
    Map 'step_3' -> '3'. Ignore 'env.*' and 'workflow.*'.
    """
    refs: Set[str] = set()

    def normalize_head(head: str) -> Optional[str]:
        if head in ("env", "workflow"):
            return None
        if head.startswith("step_"):
            s = head[len("step_"):]
            return s if s else None
        return head

    def walk(x: Any):
        if isinstance(x, str):
            for m in _STEP_REF_GENERAL_RE.finditer(x):
                head = normalize_head(m.group(1))
                if head:
                    refs.add(str(head))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(val)
    return refs


# ---------------------------
# Metrics
# ---------------------------

@dataclass
class StructuralDeltas:
    delta_nodes: int
    delta_edges: int
    ratio_nodes: float
    ratio_edges: float


@dataclass
class MinimalAugmentation:
    node_ratio_vs_min: float
    edge_ratio_vs_min: float
    node_content_f1: float = 0.0   # F1 of incremental node set (by mcp_tool)
    edge_content_f1: float = 0.0   # F1 of incremental edge set


@dataclass
class PreservationStats:
    edge_preservation_rate: float
    path2_preservation_rate: Optional[float] = None


@dataclass
class ToolChainMetrics:
    tool_name_accuracy: float   # positional match rate of mcp_tool names
    data_ref_accuracy: float    # fraction of {{ step_X.result }} refs pointing to correct step
    step_count_match: bool      # whether step counts are identical


@dataclass
class Q3Metrics:
    spr: PreservationStats
    deltas: StructuralDeltas
    minimality: MinimalAugmentation
    ged_nodes_edges: int
    mcp_call_detected: bool
    mcp_call_confidence: float


def compute_deltas(W_simple: GraphView, W_prime: GraphView) -> StructuralDeltas:
    dn = max(0, len(W_prime.nodes) - len(W_simple.nodes))
    de = max(0, len(W_prime.edges) - len(W_simple.edges))
    ratio_nodes = (len(W_prime.nodes) / max(1, len(W_simple.nodes)))
    ratio_edges = (len(W_prime.edges) / max(1, len(W_simple.edges)))
    return StructuralDeltas(dn, de, ratio_nodes, ratio_edges)


def _make_path2_set(g: GraphView) -> Set[Tuple[str, str, str]]:
    succ: Dict[str, Set[str]] = {}
    for e in g.edges:
        succ.setdefault(e.src, set()).add(e.dst)
    triples: Set[Tuple[str, str, str]] = set()
    for a, Bs in succ.items():
        for b in Bs:
            for c in succ.get(b, set()):
                triples.add((a, b, c))
    return triples


def compute_preservation(W_simple: GraphView, W_prime: GraphView) -> PreservationStats:
    edges_base = {(e.src, e.dst, e.kind) for e in W_simple.edges}
    edges_prime = {(e.src, e.dst, e.kind) for e in W_prime.edges}
    edge_pres = len(edges_base & edges_prime) / max(1, len(edges_base))

    path2_base = _make_path2_set(W_simple)
    if path2_base:
        path2_prime = _make_path2_set(W_prime)
        path2_pres = len(path2_base & path2_prime) / max(1, len(path2_base))
    else:
        path2_pres = None

    return PreservationStats(edge_preservation_rate=edge_pres, path2_preservation_rate=path2_pres)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_minimality(W_simple: GraphView, W_gold: GraphView, W_prime: GraphView) -> MinimalAugmentation:
    dn_star = max(0, len(W_gold.nodes) - len(W_simple.nodes))
    de_star = max(0, len(W_gold.edges) - len(W_simple.edges))
    dn = max(0, len(W_prime.nodes) - len(W_simple.nodes))
    de = max(0, len(W_prime.edges) - len(W_simple.edges))

    def safe_ratio(num: int, den: int) -> float:
        if den <= 0:
            return 1.0 if num <= 0 else 999.0
        return num / max(1, den)

    # Content-level F1 for incremental nodes (by mcp_tool name)
    simple_nodes = W_simple.nodes
    gold_inc_tools = {
        W_gold.node_attrs.get(n, {}).get("mcp_tool", "")
        for n in (W_gold.nodes - simple_nodes)
    } - {""}
    prime_inc_tools = {
        W_prime.node_attrs.get(n, {}).get("mcp_tool", "")
        for n in (W_prime.nodes - simple_nodes)
    } - {""}

    if gold_inc_tools or prime_inc_tools:
        tp_tools = gold_inc_tools & prime_inc_tools
        prec = len(tp_tools) / max(1, len(prime_inc_tools))
        rec = len(tp_tools) / max(1, len(gold_inc_tools))
        node_content_f1 = _f1(prec, rec)
    else:
        node_content_f1 = 1.0  # both empty => perfect

    # Content-level F1 for incremental edges
    simple_edges = {e.as_tuple() for e in W_simple.edges}
    gold_inc_edges = W_gold.edge_set() - simple_edges
    prime_inc_edges = W_prime.edge_set() - simple_edges

    if gold_inc_edges or prime_inc_edges:
        tp_edges = gold_inc_edges & prime_inc_edges
        prec_e = len(tp_edges) / max(1, len(prime_inc_edges))
        rec_e = len(tp_edges) / max(1, len(gold_inc_edges))
        edge_content_f1 = _f1(prec_e, rec_e)
    else:
        edge_content_f1 = 1.0

    return MinimalAugmentation(
        node_ratio_vs_min=safe_ratio(dn, dn_star),
        edge_ratio_vs_min=safe_ratio(de, de_star),
        node_content_f1=round(node_content_f1, 4),
        edge_content_f1=round(edge_content_f1, 4),
    )


def compute_tool_chain_accuracy(W_prime: GraphView, W_gold: GraphView) -> ToolChainMetrics:
    """
    Compare the tool call chain of W_prime against W_gold using positional
    alignment (not step_id alignment, since IDs may differ).

    Returns ToolChainMetrics with:
    - tool_name_accuracy: fraction of positions where mcp_tool names match
    - data_ref_accuracy: fraction of {{ step_X }} references that point to the
      correct producer (by position)
    - step_count_match: whether the two workflows have the same number of steps
    """
    # Build ordered tool lists (sorted by step_id as int if possible, else string)
    def _ordered_ids(g: GraphView) -> List[str]:
        def _sort_key(s: str):
            try:
                return (0, int(s))
            except ValueError:
                return (1, s)
        return sorted(g.nodes, key=_sort_key)

    gold_ids = _ordered_ids(W_gold)
    prime_ids = _ordered_ids(W_prime)

    step_count_match = len(gold_ids) == len(prime_ids)

    # Tool name accuracy (positional)
    compare_len = min(len(gold_ids), len(prime_ids))
    if compare_len == 0:
        return ToolChainMetrics(
            tool_name_accuracy=1.0 if not gold_ids and not prime_ids else 0.0,
            data_ref_accuracy=1.0 if not gold_ids and not prime_ids else 0.0,
            step_count_match=step_count_match,
        )

    matches = 0
    for i in range(compare_len):
        g_tool = W_gold.node_attrs.get(gold_ids[i], {}).get("mcp_tool", "")
        p_tool = W_prime.node_attrs.get(prime_ids[i], {}).get("mcp_tool", "")
        if g_tool and g_tool == p_tool:
            matches += 1
    # Denominator is max of the two lengths to penalise extra/missing steps
    tool_name_accuracy = matches / max(len(gold_ids), len(prime_ids))

    # Data reference accuracy
    # Build positional mapping: gold step_id -> position, prime step_id -> position
    gold_id_to_pos = {sid: i for i, sid in enumerate(gold_ids)}
    prime_id_to_pos = {sid: i for i, sid in enumerate(prime_ids)}

    total_refs = 0
    correct_refs = 0
    for i in range(compare_len):
        p_sid = prime_ids[i]
        g_sid = gold_ids[i]
        p_refs = W_prime.data_refs.get(p_sid, set())
        g_refs = W_gold.data_refs.get(g_sid, set())

        if not g_refs:
            continue

        for g_ref in g_refs:
            total_refs += 1
            g_ref_pos = gold_id_to_pos.get(g_ref)
            if g_ref_pos is None:
                continue
            # Check if any of the prime refs point to the same positional step
            for p_ref in p_refs:
                p_ref_pos = prime_id_to_pos.get(p_ref)
                if p_ref_pos == g_ref_pos:
                    correct_refs += 1
                    break

    data_ref_accuracy = correct_refs / max(1, total_refs)

    return ToolChainMetrics(
        tool_name_accuracy=round(tool_name_accuracy, 4),
        data_ref_accuracy=round(data_ref_accuracy, 4),
        step_count_match=step_count_match,
    )


def approximate_ged_nodes_edges(W_a: GraphView, W_b: GraphView) -> int:
    node_add = len(W_b.nodes - W_a.nodes)
    node_del = len(W_a.nodes - W_b.nodes)
    edge_add = len(W_b.edge_set() - W_a.edge_set())
    edge_del = len(W_a.edge_set() - W_b.edge_set())
    return node_add + node_del + edge_add + edge_del


# ---------------------------
# Static check: does run_workflow.py really call MCP tools?
# ---------------------------

_MCP_CLIENT_RE = re.compile(
    r"""(?x)
    (?:from\s+fastmcp\s+import\s+Client|import\s+fastmcp|from\s+mcp\s+import\s+Client|from\s+.*mcp.*\s+import\s+Client)
    """
)

_ASYNC_WITH_CLIENT_RE = re.compile(r"async\s+with\s+Client\s*\(", re.MULTILINE)
_LIST_TOOLS_RE = re.compile(r"\.list_tools\s*\(", re.MULTILINE)
_INVOKE_TOOL_RE = re.compile(
    r"""(?x)
    \.(?:call_tool|invoke|run_tool|tools\[[^]]+\]\()|
    client\.(?:tools|tool|call|invoke)
    """
)


def inspect_mcp_usage(py_code: str) -> Tuple[bool, float, Dict[str, bool]]:
    flags = {
        "import_client": bool(_MCP_CLIENT_RE.search(py_code)),
        "async_with_client": bool(_ASYNC_WITH_CLIENT_RE.search(py_code)),
        "list_tools": bool(_LIST_TOOLS_RE.search(py_code)),
        "invoke_tool": bool(_INVOKE_TOOL_RE.search(py_code)),
    }
    score = 0.0
    score += 0.3 if flags["import_client"] else 0.0
    score += 0.3 if flags["async_with_client"] else 0.0
    score += 0.2 if flags["invoke_tool"] else 0.0
    score += 0.2 if flags["list_tools"] else 0.0
    return (score >= 0.6, min(1.0, score), flags)


# ---------------------------
# Serialization helper
# ---------------------------

def to_serializable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, set):
        return sorted(list(obj))
    if isinstance(obj, (list, tuple)):
        return [to_serializable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    return obj
