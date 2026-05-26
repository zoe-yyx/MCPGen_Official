"""

"""

from typing import Dict, List, Any, Union
from pathlib import Path

from .workflow_helpers import extract_linear_path



def flatten_dependencies(deps: Union[List, Dict]) -> List[str]:
    """
    
    Args:
    
    Returns:
    """
    if isinstance(deps, list):
        return deps
    elif isinstance(deps, dict):
        all_ids = []
        for branch_ids in deps.values():
            if isinstance(branch_ids, list):
                all_ids.extend(branch_ids)
        return all_ids
    else:
        return []


def is_branch_step(deps: Union[List, Dict]) -> bool:
    """
    
    Args:
    
    Returns:
    """
    if isinstance(deps, dict):
        return True
    elif isinstance(deps, list):
        return len(deps) > 1
    return False


def is_conditional_branch(deps: Union[List, Dict]) -> bool:
    return isinstance(deps, dict)


def get_branch_info(deps: Union[List, Dict]) -> Dict[str, List[str]]:
    """
    
    Returns:
    """
    if isinstance(deps, dict):
        return deps
    elif isinstance(deps, list) and len(deps) > 1:
        return {f"branch_{i+1}": [dep] for i, dep in enumerate(deps)}
    elif isinstance(deps, list) and len(deps) == 1:
        return {"next": deps}
    else:
        return {}


def trace_branch_path(start_id: str, dependencies: Dict, max_depth: int = 20) -> List[str]:
    """
    
    Args:
    
    Returns:
    """
    path = [start_id]
    current = start_id
    visited = {start_id}
    
    for _ in range(max_depth):
        if current not in dependencies:
            break
        
        nexts = dependencies[current]
        flat_nexts = flatten_dependencies(nexts)
        
        if len(flat_nexts) == 0:
            break
        
        if len(flat_nexts) == 1 and not is_conditional_branch(nexts):
            next_step = flat_nexts[0]
            if next_step in visited:
                break
            path.append(next_step)
            visited.add(next_step)
            current = next_step
        else:
            break
    
    return path


def find_main_path_until_branch(execution_order: List[str], dependencies: Dict) -> List[str]:
    """
    
    Args:
    
    Returns:
    """
    if not execution_order:
        return []
    
    main_path = [execution_order[0]]
    current = execution_order[0]
    visited = {current}
    
    while current in dependencies:
        nexts = dependencies[current]
        
        if is_branch_step(nexts):
            break
        
        flat_nexts = flatten_dependencies(nexts)
        if len(flat_nexts) == 1:
            next_step = flat_nexts[0]
            if next_step in visited:
                break
            main_path.append(next_step)
            visited.add(next_step)
            current = next_step
        else:
            break
    
    return main_path


def find_first_branch_point(dependencies: Dict, execution_order: List[str] = None) -> tuple:
    """
    
    Returns:
    """
    if execution_order:
        for step_id in execution_order:
            if step_id in dependencies:
                deps = dependencies[step_id]
                if is_branch_step(deps):
                    return step_id, deps
    else:
        for step_id, deps in dependencies.items():
            if is_branch_step(deps):
                return step_id, deps
    
    return None, None


def format_path(path: List[str]) -> str:
    if not path:
        return "(empty)"
    return " -> ".join(path)


def visualize_workflow_structure(
    dependencies: Dict[str, Union[List, Dict]], 
    execution_order: List[str],
    prefix: str = "📋",
    title: str = "Structure"
) -> List[str]:
    """
    
    Args:
    
    Returns:
    """
    lines = [f"{prefix} {title}:"]
    
    if not execution_order:
        lines.append("  (empty workflow)")
        return lines
    
    main_path = find_main_path_until_branch(execution_order, dependencies)
    lines.append(f"  Main Path: {format_path(main_path)}")
    
    branch_point_id, branch_deps = find_first_branch_point(dependencies, execution_order)
    
    if branch_point_id and branch_deps:
        lines.append(f"  Branches from {branch_point_id}:")
        
        if is_conditional_branch(branch_deps):
            for branch_name, branch_targets in branch_deps.items():
                if branch_targets:
                    first_target = branch_targets[0]
                    branch_path = trace_branch_path(first_target, dependencies)
                    lines.append(f"    {branch_name}: {format_path(branch_path)}")
        else:
            for i, branch_id in enumerate(branch_deps, 1):
                branch_path = trace_branch_path(branch_id, dependencies)
                lines.append(f"    Branch {i}: {format_path(branch_path)}")
    
    return lines



def generate_evaluation_report(
    results: Dict,
    mcp_tools: List[Any],
    reference_answer: Dict,
    generated_workflow_steps: List[Dict],
    output_path: Path = None
) -> str:
    """
    
    Args:
    
    Returns:
    """
    lines = [
        "=" * 80,
        "Workflow Orchestration Evaluation Report (MCP Version)",
        "=" * 80,
        f"Timestamp: {results['timestamp']}",
        f"MCP Tools Used: {len(mcp_tools)} tools",
        "",
    ]
    
    if mcp_tools:
        lines.append("📦 MCP Tools:")
        for tool in mcp_tools:
            desc = tool.description if hasattr(tool, 'description') else str(tool.get('description', ''))
            name = tool.name if hasattr(tool, 'name') else str(tool.get('name', ''))
            lines.append(f"   - {name}: {desc[:60]}...")
        lines.append("")
    
    order_metrics = results['metrics']['order_accuracy']
    
    if order_metrics.get('evaluation_type') == 'branching_workflow':
        lines.extend([
            "=" * 80,
            "EXECUTION ORDER EVALUATION (BRANCHING WORKFLOW)",
            "=" * 80,
            "",
            "📊 KEY METRICS:",
            "",
            f"1. Overall Path Correctness:      {order_metrics['overall_path_correctness']:.2%}"
        ])
        
        lines.extend([
            "=" * 80,
            "DETAILED ANALYSIS",
            "=" * 80,
            "",
        ])
        
        overall_details = order_metrics['overall_path_details']
        lines.extend([
            "1️⃣  OVERALL PATH CORRECTNESS",
            f"   - Dependency Satisfaction: {overall_details['dependency_satisfaction']:.2%}",
            f"   - Completeness: {overall_details['completeness']:.2%}",
            f"   - Satisfied Dependencies: {overall_details['satisfied_dependencies']}/{overall_details['total_dependencies']}",
        ])
        
        if overall_details['missing_steps']:
            lines.append(f"   - Missing Steps: {overall_details['missing_steps']}")
        if overall_details['extra_steps']:
            lines.append(f"   - Extra Steps: {overall_details['extra_steps']}")
        
        if overall_details['violations']:
            lines.append(f"   - Violations: {len(overall_details['violations'])}")
            for v in overall_details['violations'][:3]:
                lines.append(f"     • {v['reason']}")
        
        lines.append("")
        
    else:
        lines.extend([
            "=" * 80,
            "EXECUTION ORDER EVALUATION (LINEAR WORKFLOW)",
            "=" * 80,
            "",
            "📊 KEY METRIC:",
            "",
            f"Overall Path Correctness: {order_metrics['overall_path_correctness']:.2%}",
            "",
            "=" * 80,
            "DETAILED ANALYSIS",
            "=" * 80,
            "",
            f"- Exact Match: {'✓' if order_metrics['exact_match'] else '✗'}",
            f"- LCS Similarity: {order_metrics.get('lcs_similarity', 0):.2%}",
            f"- Completeness: {order_metrics.get('completeness', 0):.2%}",
            f"- Mean Position Error: {order_metrics['position_errors']['mean']:.2f}",
            f"- Max Position Error: {order_metrics['position_errors']['max']}",
            "",
        ])
    
    lines.extend([
        "=" * 80,
        "OTHER METRICS",
        "=" * 80,
        "",
    ])
    
    dep_metrics = results['metrics']['dependency_accuracy']
    lines.extend([
        "Dependency Accuracy (next_steps)",
        f"- Accuracy: {dep_metrics['accuracy']:.2%}",
        f"- Correct Edges: {dep_metrics['correct_edges']}/{dep_metrics['total_edges']}",
        f"- Missing Edges: {len(dep_metrics['missing_edges'])}",
        f"- Extra Edges: {len(dep_metrics['extra_edges'])}",
        "",
    ])
    
    cf_metrics = results['metrics']['control_flow_accuracy']
    lines.extend([
        "Control Flow Accuracy",
        f"- Accuracy: {cf_metrics['accuracy']:.2%}",
        "",
    ])

    err_metrics = results['metrics']['error_propagation']
    lines.extend([
        "Error Propagation Rate",
        f"- Propagation Rate: {err_metrics['error_propagation_rate']:.2%}",
        "",
    ])
    
    lines.extend([
        "=" * 80,
        "WORKFLOW STRUCTURE COMPARISON",
        "=" * 80,
        "",
    ])
    
    gen_deps = {}
    if generated_workflow_steps:
        for step in generated_workflow_steps:
            if step.get('next_steps'):
                gen_deps[step['step_id']] = step['next_steps']
    
    ref_deps = reference_answer.get('dependencies', {})
    ref_order = reference_answer.get('execution_order', [])
    gen_order = results.get('generated_order', [])
    
    ref_has_branches = any(is_branch_step(v) for v in ref_deps.values())
    gen_has_branches = any(is_branch_step(v) for v in gen_deps.values())
    
    if ref_has_branches:
        ref_viz_lines = visualize_workflow_structure(
            ref_deps, ref_order, 
            prefix="📋", title="Reference Structure"
        )
        lines.extend(ref_viz_lines)
    else:
        lines.extend([
            "📋 Reference Order:",
            f"  {' -> '.join(results['reference_order'])}",
        ])
    
    lines.append("")
    
    if gen_has_branches:
        gen_viz_lines = visualize_workflow_structure(
            gen_deps, gen_order,
            prefix="🤖", title="Generated Structure"
        )
        lines.extend(gen_viz_lines)
    else:
        lines.extend([
            "🤖 Generated Order:",
            f"  {' -> '.join(results['generated_order'])}",
        ])
    
    lines.extend([
        "",
        "=" * 80,
        "OVERALL SCORE",
        "=" * 80,
        f"Total Score: {results['overall_score']:.2%}",
        "",
    ])
    
    if results['overall_score'] >= 0.95:
        lines.append("✅ EXCELLENT")
    elif results['overall_score'] >= 0.80:
        lines.append("✅ PASSED")
    elif results['overall_score'] >= 0.60:
        lines.append("⚠️  NEEDS IMPROVEMENT")
    else:
        lines.append("❌ FAILED")
    
    lines.append("=" * 80)
    
    report = "\n".join(lines)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
    
    return report
