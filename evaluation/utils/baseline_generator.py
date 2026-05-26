"""
utils/baseline_generator.py

Generate a baseline `workflow_simple.json` from the full `workflow.json`
by keeping only the first ceil(N/2) workflow steps.

- Preserves step ordering from `workflow_steps`
- Truncates `next_steps` references that point to removed steps
- Ensures the result is a valid, connected sub-workflow
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, Optional, Set


def generate_baseline(
    workflow: Dict[str, Any],
    ratio: float = 0.5,
    mode: str = "prefix",
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a baseline workflow by keeping ceil(N * ratio) steps.

    Args:
        workflow: Full workflow dict (must contain ``workflow_steps``).
        ratio: Fraction of steps to keep (default 0.5).
        mode: ``"prefix"`` keeps the first N steps (original behavior);
              ``"random"`` randomly samples N steps (preserving original order).
        seed: Random seed for reproducibility (only used when mode="random").

    Returns:
        A new workflow dict with truncated steps and pruned edges.
    """
    steps = workflow.get("workflow_steps") or workflow.get("steps") or []
    if not steps:
        return workflow  # nothing to truncate

    keep_count = max(1, math.ceil(len(steps) * ratio))

    if mode == "random":
        rng = random.Random(seed)
        indices = sorted(rng.sample(range(len(steps)), keep_count))
        kept_steps = [steps[i] for i in indices]
    else:
        kept_steps = steps[:keep_count]

    # Set of step_ids that survive
    kept_ids: Set[str] = {str(s.get("step_id", "")).strip() for s in kept_steps}

    # Prune next_steps / else_steps that point outside the kept set
    pruned_steps = []
    for step in kept_steps:
        new_step = dict(step)
        for edge_key in ("next_steps", "else_steps"):
            if edge_key in new_step and isinstance(new_step[edge_key], list):
                new_step[edge_key] = [
                    sid for sid in new_step[edge_key]
                    if str(sid).strip() in kept_ids
                ]
        # Also prune error_handler if it points outside
        err = new_step.get("error_handler")
        if isinstance(err, str) and str(err).strip() not in kept_ids:
            new_step["error_handler"] = None
        elif isinstance(err, dict):
            goto = err.get("goto") or err.get("step")
            if goto and str(goto).strip() not in kept_ids:
                new_step["error_handler"] = None
        pruned_steps.append(new_step)

    # Build the baseline workflow, preserving top-level metadata
    baseline: Dict[str, Any] = {}
    if "workflow" in workflow:
        baseline["workflow"] = workflow["workflow"]
    if "configuration" in workflow:
        baseline["configuration"] = workflow["configuration"]

    # Use the same key as the source
    if "workflow_steps" in workflow:
        baseline["workflow_steps"] = pruned_steps
    else:
        baseline["steps"] = pruned_steps

    return baseline


def ensure_baseline(
    project_dir: Path,
    baseline_name: str = "workflow_simple.json",
    gold_candidates: Optional[list] = None,
    ratio: float = 0.5,
    mode: str = "prefix",
    seed: Optional[int] = None,
) -> Path:
    """
    If the baseline file does not exist in *project_dir*, generate it
    from ``workflow.json`` (or the first found gold candidate).

    When *mode* is ``"random"``, the baseline filename is changed to
    ``workflow_simple_random.json`` so that both modes can coexist.

    Returns:
        Path to the (possibly newly-created) baseline file.

    Raises:
        FileNotFoundError: if no gold workflow is available to derive from.
    """
    stem = Path(baseline_name).stem
    ratio_tag = f"{ratio:.2f}".replace(".", "")  # 0.5 -> "050", 0.3 -> "030"
    if mode == "random":
        baseline_name = f"{stem}_r{ratio_tag}_random.json"
    else:
        baseline_name = f"{stem}_r{ratio_tag}.json"

    baseline_path = project_dir / baseline_name
    if baseline_path.exists():
        return baseline_path

    if gold_candidates is None:
        gold_candidates = ["workflow.json", "workflow_full.json"]

    gold_path = None
    for name in gold_candidates:
        candidate = project_dir / name
        if candidate.exists():
            gold_path = candidate
            break

    if gold_path is None:
        raise FileNotFoundError(
            f"Cannot generate baseline: no gold workflow found in {project_dir} "
            f"(tried {gold_candidates})"
        )

    with gold_path.open("r", encoding="utf-8") as f:
        full_workflow = json.load(f)

    baseline = generate_baseline(full_workflow, ratio=ratio, mode=mode, seed=seed)
    baseline_path.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return baseline_path
