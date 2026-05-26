"""
tasks/workflow_ordering.py



"""

import json
import random
import copy
import traceback
from typing import Dict, List, Any, Tuple
from pathlib import Path
from datetime import datetime
import sys
import asyncio
from tqdm import tqdm
import numpy as np

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
from utils.llm_interface import LLMInterface
from core.config import EvaluationConfig, LLMConfig
from utils.evaluate_tools import obfuscate_steps, parse_llm_output
from utils.workflow_helpers import (
    calculate_lcs_similarity, calculate_position_errors, find_step_references,
    extract_linear_path, evaluate_dependency_satisfaction, generate_summary_report,
    check_has_branches, extract_dependencies, extract_dataflow, extract_control_flow
)
from utils.report_generator import generate_evaluation_report
from utils.error_propagation import calculate_error_propagation

NUM_RUNS = 5


# ==================== DualLogger ====================

class DualLogger:

    def __init__(self, filepath):
        self.filepath = filepath
        self.file = None
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def __enter__(self):
        self.file = open(self.filepath, 'w', encoding='utf-8')
        sys.stdout = self
        sys.stderr = self
        return self

    def __exit__(self, exc_type, exc_value, tb):
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        if self.file:
            self.file.close()

    def write(self, message):
        self.stdout.write(message)
        if self.file:
            self.file.write(message)
            self.file.flush()

    def flush(self):
        self.stdout.flush()
        if self.file:
            self.file.flush()

    def fileno(self):
        return self.stdout.fileno()

    def isatty(self):
        return self.stdout.isatty()



class WorkflowEvaluationSystem:

    def __init__(self, reference_workflow_path: str, seed: int = 42, obfuscate: bool = True):
        self.reference_workflow = self._load_workflow(reference_workflow_path)
        self.seed = seed
        self.obfuscate = obfuscate
        random.seed(seed)

        self.reference_answer = self._extract_reference_answer()
        self.id_mapping = None
        self.generated_workflow_steps = None

    def _load_workflow(self, path: str) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _extract_reference_answer(self) -> Dict:
        steps = self.reference_workflow['workflow_steps']
        return {
            'execution_order': [s['step_id'] for s in steps],
            'steps_detail': {s['step_id']: s for s in steps},
            'dependencies': extract_dependencies(steps),
            'dataflow': extract_dataflow(steps),
            'control_flow': extract_control_flow(steps),
            'step_count': len(steps),
            'has_branches': check_has_branches(steps),
        }

    def reset_for_new_run(self, seed: int):
        self.seed = seed
        random.seed(seed)
        self.reference_answer = self._extract_reference_answer()
        self.id_mapping = None
        self.generated_workflow_steps = None


    def generate_shuffled_workflow(self) -> Dict:
        shuffled = copy.deepcopy(self.reference_workflow)
        steps = shuffled['workflow_steps']
        original_ids = [s['step_id'] for s in steps]

        if self.obfuscate:
            self.id_mapping = obfuscate_steps(steps)
            self.reference_answer['execution_order'] = [
                self.id_mapping[old_id] for old_id in original_ids
            ]
            new_dependencies = {}
            for k, vs in self.reference_answer['dependencies'].items():
                new_k = self.id_mapping.get(k, k)
                if isinstance(vs, list):
                    new_dependencies[new_k] = [self.id_mapping.get(v, v) for v in vs]
                elif isinstance(vs, dict):
                    new_v = {}
                    for branch_name, branch_ids in vs.items():
                        new_v[branch_name] = [self.id_mapping.get(bid, bid) for bid in branch_ids]
                    new_dependencies[new_k] = new_v
                else:
                    new_dependencies[new_k] = vs
            self.reference_answer['dependencies'] = new_dependencies

            self.reference_answer['dataflow'] = {
                self.id_mapping.get(k, k): [self.id_mapping.get(v, v) for v in vs]
                for k, vs in self.reference_answer['dataflow'].items()
            }

            new_control_flow = {}
            for k, v in self.reference_answer['control_flow'].items():
                new_k = self.id_mapping[k]
                new_v = {}
                if 'else_steps' in v:
                    new_v['else_steps'] = [self.id_mapping[x] for x in v['else_steps']]
                if 'error_handler' in v:
                    new_v['error_handler'] = self.id_mapping[v['error_handler']]
                new_control_flow[new_k] = new_v
            self.reference_answer['control_flow'] = new_control_flow

        random.shuffle(steps)
        for step in steps:
            step.pop('next_steps', None)
        shuffled['workflow_steps'] = steps
        return shuffled


    def build_prompt(self, shuffled_workflow: Dict) -> str:
        workflow_json = json.dumps(shuffled_workflow['workflow_steps'], indent=2, ensure_ascii=False)

        return f"""You are an AI agent tasked with reconstructing a workflow whose steps have been shuffled.
**IMPORTANT INSTRUCTIONS:**
- Step IDs are randomized (e.g., '3f94c550') and DO NOT reflect execution order
- DO NOT sort by step_id or by name alphabetically
- Infer the correct execution order based on:
  1. Step types and tool semantics (validation → information → trigger → monitoring → conditional → termination → output)
  2. Data dependencies: {{{{step_X.output}}}} means step X must execute before the current step
  3. Conditional logic: steps may reference {{{{step_Y.condition_result}}}} to determine branching

**BRANCHING RULES:**
- If a conditional step has multiple outcome paths, include ALL target steps in its next_steps array
- Example: A conditional check may lead to both a success termination and a failure termination
- Both branches should be listed in the conditional step's next_steps: ["success_step_id", "failure_step_id"]

**OUTPUT FORMAT:**
Return ONLY a JSON object (no prose, no backticks, no markdown):
{{"workflow_steps": [{{"step_id": "<id>", "next_steps": ["<id>", ...]}}, ...]}}

**SHUFFLED WORKFLOW:**
{workflow_json}

Return the workflow_steps array in the correct execution order."""


    def evaluate(self, generated_workflow: Dict) -> Dict:
        gen_steps = generated_workflow['workflow_steps']
        gen_order = [s['step_id'] for s in gen_steps]
        self.generated_workflow_steps = gen_steps

        results = {
            'timestamp': datetime.now().isoformat(),
            'reference_order': self.reference_answer['execution_order'],
            'generated_order': gen_order,
            'metrics': {},
        }

        results['metrics']['order_accuracy'] = self._evaluate_order(gen_order)
        results['metrics']['dependency_accuracy'] = self._evaluate_dependencies(gen_steps)
        results['metrics']['control_flow_accuracy'] = self._evaluate_control_flow(gen_steps)
        results['metrics']['error_propagation'] = self._evaluate_error_propagation(gen_steps)

        results['overall_score'] = self._calculate_overall_score(results['metrics'])
        return results

    def _evaluate_order(self, generated_order: List[str]) -> Dict:
        ref_order = self.reference_answer['execution_order']
        ref_deps = self.reference_answer['dependencies']

        has_branches = any(
            len(nexts) > 1 for nexts in ref_deps.values() if isinstance(nexts, list)
        )

        if has_branches:
            return self._evaluate_branching_workflow(self.generated_workflow_steps)
        else:
            return self._evaluate_linear_order(generated_order, ref_order)

    def _evaluate_branching_workflow(self, gen_steps: List[Dict]) -> Dict:
        ref_deps = self.reference_answer['dependencies']
        ref_order = self.reference_answer['execution_order']

        gen_deps = {}
        for step in gen_steps:
            if step.get('next_steps'):
                gen_deps[step['step_id']] = step['next_steps']
        gen_order = [s['step_id'] for s in gen_steps]

        results = {'evaluation_type': 'branching_workflow'}

        ref_branch_points = [
            (k, v) for k, v in ref_deps.items() if isinstance(v, list) and len(v) > 1
        ]
        if not ref_branch_points:
            return self._evaluate_linear_order(gen_order, ref_order)

        dependency_result = evaluate_dependency_satisfaction(ref_deps, gen_order)

        ref_steps_set = set(ref_order)
        gen_steps_set = set(gen_order)
        missing_steps = ref_steps_set - gen_steps_set
        extra_steps = gen_steps_set - ref_steps_set

        completeness = len(ref_steps_set & gen_steps_set) / len(ref_steps_set) if ref_steps_set else 1.0
        overall_path_correctness = dependency_result['satisfaction_rate'] * completeness

        results['overall_path_correctness'] = overall_path_correctness
        results['overall_path_details'] = {
            'dependency_satisfaction': dependency_result['satisfaction_rate'],
            'completeness': completeness,
            'missing_steps': list(missing_steps),
            'extra_steps': list(extra_steps),
            'satisfied_dependencies': dependency_result['satisfied_dependencies'],
            'total_dependencies': dependency_result['total_dependencies'],
            'violations': dependency_result['violations'],
        }
        return results

    def _evaluate_linear_order(self, generated_order: List[str], ref_order: List[str]) -> Dict:
        exact_match = (generated_order == ref_order)
        lcs_score = calculate_lcs_similarity(generated_order, ref_order)
        position_errors = calculate_position_errors(generated_order, ref_order)

        ref_steps_set = set(ref_order)
        gen_steps_set = set(generated_order)
        completeness = len(ref_steps_set & gen_steps_set) / len(ref_steps_set) if ref_steps_set else 1.0

        return {
            'evaluation_type': 'linear',
            'exact_match': exact_match,
            'overall_path_correctness': lcs_score * completeness,
            'lcs_similarity': lcs_score,
            'completeness': completeness,
            'position_errors': position_errors,
        }

    def _evaluate_dependencies(self, gen_steps: List[Dict]) -> Dict:
        ref_deps = self.reference_answer['dependencies']
        gen_deps = {}
        for step in gen_steps:
            if step.get('next_steps'):
                gen_deps[step['step_id']] = set(step['next_steps'])

        total_edges = 0
        correct_edges = 0
        missing_edges = []
        extra_edges = []

        for sid, ref_nexts in ref_deps.items():
            if isinstance(ref_nexts, list):
                for next_id in ref_nexts:
                    total_edges += 1
                    if next_id in gen_deps.get(sid, set()):
                        correct_edges += 1
                    else:
                        missing_edges.append((sid, next_id))

        for sid, gen_nexts in gen_deps.items():
            for next_id in gen_nexts:
                if sid not in ref_deps or (isinstance(ref_deps[sid], list) and next_id not in ref_deps[sid]):
                    extra_edges.append((sid, next_id))

        accuracy = correct_edges / total_edges if total_edges > 0 else 1.0
        return {
            'accuracy': accuracy,
            'total_edges': total_edges,
            'correct_edges': correct_edges,
            'missing_edges': missing_edges,
            'extra_edges': extra_edges,
            'score': accuracy,
        }

    def _evaluate_control_flow(self, gen_steps: List[Dict]) -> Dict:
        ref_control = self.reference_answer['control_flow']
        if not ref_control:
            return {'accuracy': 1.0, 'score': 1.0, 'details': 'No control flow in reference'}

        gen_control = {}
        for step in gen_steps:
            cf = {}
            if step.get('else_steps'):
                cf['else_steps'] = set(step['else_steps'])
            if step.get('error_handler'):
                cf['error_handler'] = step['error_handler']
            if cf:
                gen_control[step['step_id']] = cf

        total_controls = 0
        correct_controls = 0
        details = {'else_steps': {}, 'error_handler': {}}

        for sid, ref_cf in ref_control.items():
            gen_cf = gen_control.get(sid, {})
            if 'else_steps' in ref_cf:
                total_controls += len(ref_cf['else_steps'])
                ref_else = set(ref_cf['else_steps'])
                gen_else = gen_cf.get('else_steps', set())
                correct = len(ref_else & gen_else)
                correct_controls += correct
                details['else_steps'][sid] = {
                    'expected': list(ref_else), 'actual': list(gen_else), 'correct': correct
                }
            if 'error_handler' in ref_cf:
                total_controls += 1
                if gen_cf.get('error_handler') == ref_cf['error_handler']:
                    correct_controls += 1
                    details['error_handler'][sid] = 'correct'
                else:
                    details['error_handler'][sid] = {
                        'expected': ref_cf['error_handler'],
                        'actual': gen_cf.get('error_handler', None),
                    }

        accuracy = correct_controls / total_controls if total_controls > 0 else 1.0
        return {
            'accuracy': accuracy,
            'total_controls': total_controls,
            'correct_controls': correct_controls,
            'details': details,
            'score': accuracy,
        }

    def _evaluate_error_propagation(self, gen_steps: List[Dict]) -> Dict:
        return calculate_error_propagation(
            ref_order=self.reference_answer['execution_order'],
            gen_order=[s['step_id'] for s in gen_steps],
            ref_deps=self.reference_answer['dependencies'],
            gen_steps=gen_steps,
        )

    def _calculate_overall_score(self, metrics: Dict) -> float:
        order_metrics = metrics.get('order_accuracy', {})
        order_score = order_metrics.get('overall_path_correctness', 0.0)

        weights = {
            'order': 0.4,
            'dependency_accuracy': 0.2,
            'control_flow_accuracy': 0.0,
            'error_propagation': 0.4,
        }

        return (
            weights['order'] * order_score
            + weights['dependency_accuracy'] * metrics.get('dependency_accuracy', {}).get('score', 0.0)
            + weights['control_flow_accuracy'] * metrics.get('control_flow_accuracy', {}).get('score', 0.0)
            + weights['error_propagation'] * metrics.get('error_propagation', {}).get('score', 0.0)
        )


    def generate_report(self, results: Dict, output_path: Path = None) -> str:
        return generate_evaluation_report(
            results=results,
            mcp_tools=[],
            reference_answer=self.reference_answer,
            generated_workflow_steps=getattr(self, 'generated_workflow_steps', []),
            output_path=output_path
        )



def aggregate_run_results(run_results: List[Dict]) -> Dict:
    if not run_results:
        return {}

    overall_scores = []
    order_scores = []
    dependency_scores = []
    control_flow_scores = []
    error_propagation_scores = []

    for result in run_results:
        if result.get('overall_score') is not None:
            overall_scores.append(result['overall_score'])
        metrics = result.get('metrics', {})
        order_acc = metrics.get('order_accuracy', {})
        if order_acc.get('overall_path_correctness') is not None:
            order_scores.append(order_acc['overall_path_correctness'])
        dep_acc = metrics.get('dependency_accuracy', {})
        if dep_acc.get('score') is not None:
            dependency_scores.append(dep_acc['score'])
        cf_acc = metrics.get('control_flow_accuracy', {})
        if cf_acc.get('score') is not None:
            control_flow_scores.append(cf_acc['score'])
        ep_acc = metrics.get('error_propagation', {})
        if ep_acc.get('score') is not None:
            error_propagation_scores.append(ep_acc['score'])

    def calc_mean_std(scores):
        if not scores:
            return None, None
        return float(np.mean(scores)), float(np.std(scores))

    overall_mean, overall_std = calc_mean_std(overall_scores)
    order_mean, order_std = calc_mean_std(order_scores)
    dep_mean, dep_std = calc_mean_std(dependency_scores)
    cf_mean, cf_std = calc_mean_std(control_flow_scores)
    ep_mean, ep_std = calc_mean_std(error_propagation_scores)

    return {
        'num_runs': len(run_results),
        'overall_score': {'mean': overall_mean, 'std': overall_std, 'values': overall_scores},
        'metrics': {
            'order_accuracy': {'mean': order_mean, 'std': order_std, 'values': order_scores},
            'dependency_accuracy': {'mean': dep_mean, 'std': dep_std, 'values': dependency_scores},
            'control_flow_accuracy': {'mean': cf_mean, 'std': cf_std, 'values': control_flow_scores},
            'error_propagation': {'mean': ep_mean, 'std': ep_std, 'values': error_propagation_scores},
        },
    }



async def evaluate_single_project(
    project_num: int,
    project_path: Path,
    llm_interface: LLMInterface,
    project_output_dir: Path,
    num_runs: int = 5,
) -> Dict:

    workflow_path = project_path / 'workflow.json'

    if not workflow_path.exists():
        return {'status': 'skipped', 'reason': 'workflow.json not found'}

    run_results = []
    for run_idx in range(num_runs):
        print(f"\n  Run {run_idx + 1}/{num_runs}")
        run_output_dir = project_output_dir / f'run_{run_idx + 1}'
        run_output_dir.mkdir(exist_ok=True)

        try:
            seed = 42 + run_idx * 1000
            eval_system = WorkflowEvaluationSystem(
                reference_workflow_path=str(workflow_path),
                seed=seed,
                obfuscate=True,
            )

            shuffled_workflow = eval_system.generate_shuffled_workflow()

            with open(run_output_dir / 'shuffled_workflow.json', 'w', encoding='utf-8') as f:
                json.dump(shuffled_workflow, f, indent=2, ensure_ascii=False)
            with open(run_output_dir / 'reference_answer.json', 'w', encoding='utf-8') as f:
                json.dump(eval_system.reference_answer, f, indent=2, ensure_ascii=False)

            prompt = eval_system.build_prompt(shuffled_workflow)

            with open(run_output_dir / 'prompt.txt', 'w', encoding='utf-8') as f:
                f.write(prompt)

            llm_output = await llm_interface.generate_response(prompt)
            with open(run_output_dir / 'llm_response.txt', 'w', encoding='utf-8') as f:
                f.write(llm_output)

            generated_workflow = parse_llm_output(llm_output)
            with open(run_output_dir / 'generated_workflow.json', 'w', encoding='utf-8') as f:
                json.dump(generated_workflow, f, indent=2, ensure_ascii=False)

            results = eval_system.evaluate(generated_workflow)
            with open(run_output_dir / 'evaluation_results.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            run_results.append(results)
            print(f"    Overall Score = {results['overall_score']:.2%}")

        except Exception as e:
            print(f"    Run {run_idx + 1} failed: {e}")
            with open(run_output_dir / 'error.txt', 'w', encoding='utf-8') as f:
                f.write(traceback.format_exc())

    if not run_results:
        return {'status': 'failed', 'error': 'All runs failed'}

    aggregated = aggregate_run_results(run_results)
    aggregated['status'] = 'success'
    aggregated['successful_runs'] = len(run_results)
    aggregated['total_runs'] = num_runs

    with open(workflow_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    aggregated['mcp_tools_count'] = len({s.get('tool', '') for s in wf.get('workflow_steps', []) if s.get('tool')})

    with open(project_output_dir / 'aggregated_results.json', 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print(f"\n  Aggregated ({len(run_results)}/{num_runs} runs): "
          f"{aggregated['overall_score']['mean']:.2%} +/- {aggregated['overall_score']['std']:.2%}")

    return aggregated



async def evaluate_model(
    model_name: str,
    llm_interface: LLMInterface,
    mcp_projects: List[Tuple[int, Path]],
    output_root_dir: Path,
    num_runs: int = 5,
    force_rerun: bool = False,
) -> Dict:

    model_output_dir = output_root_dir / model_name
    model_summary_path = model_output_dir / 'model_summary.json'

    if not force_rerun and model_summary_path.exists():
        print(f"\n  SKIP {model_name} (already evaluated, use --force to re-run)")
        with open(model_summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    print(f"\n{'='*80}")
    print(f"EVALUATING MODEL: {model_name}")
    print(f"{'='*80}")

    model_output_dir.mkdir(exist_ok=True, parents=True)

    summary_results = {
        'model_name': model_name,
        'num_runs_per_project': num_runs,
        'total': len(mcp_projects),
        'success': 0,
        'skipped': 0,
        'failed': 0,
        'details': [],
    }

    for project_num, project_path in tqdm(mcp_projects, desc=f"Projects ({model_name})"):
        print(f"\n{'='*60}")
        print(f"Processing mcp_project{project_num}")
        print(f"{'='*60}")

        project_output_dir = model_output_dir / str(project_num)
        project_output_dir.mkdir(exist_ok=True)

        log_file_path = project_output_dir / 'execution_log.txt'

        try:
            with DualLogger(log_file_path):
                result = await evaluate_single_project(
                    project_num=project_num,
                    project_path=project_path,
                    llm_interface=llm_interface,
                    project_output_dir=project_output_dir,
                    num_runs=num_runs,
                )
                result['project_num'] = project_num

                if result['status'] == 'success':
                    summary_results['success'] += 1
                elif result['status'] == 'skipped':
                    summary_results['skipped'] += 1
                else:
                    summary_results['failed'] += 1

                summary_results['details'].append(result)

        except Exception as e:
            print(f"\n  FATAL ERROR in mcp_project{project_num}: {e}")
            summary_results['failed'] += 1
            summary_results['details'].append({
                'project_num': project_num,
                'status': 'failed',
                'error': str(e),
            })

    with open(model_summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary_results, f, indent=2, ensure_ascii=False)

    model_report = generate_summary_report(summary_results)
    with open(model_output_dir / 'model_summary_report.txt', 'w', encoding='utf-8') as f:
        f.write(model_report)

    return summary_results




def generate_cross_model_report(all_model_results: Dict) -> str:
    lines = [
        "=" * 100,
        "CROSS-MODEL COMPARISON REPORT",
        f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 100,
        "",
    ]

    model_stats = {}
    for model_name, results in all_model_results.items():
        overall_means = []
        order_means = []
        dep_means = []
        cf_means = []
        ep_means = []

        for detail in results.get('details', []):
            if detail.get('status') == 'success':
                overall = detail.get('overall_score', {})
                if isinstance(overall, dict) and overall.get('mean') is not None:
                    overall_means.append(overall['mean'])

                metrics = detail.get('metrics', {})
                for key, lst in [('order_accuracy', order_means),
                                 ('dependency_accuracy', dep_means),
                                 ('control_flow_accuracy', cf_means),
                                 ('error_propagation', ep_means)]:
                    v = metrics.get(key, {})
                    if isinstance(v, dict) and v.get('mean') is not None:
                        lst.append(v['mean'])

        def safe_mean(lst):
            return float(np.mean(lst)) if lst else None

        model_stats[model_name] = {
            'overall': safe_mean(overall_means),
            'order': safe_mean(order_means),
            'dependency': safe_mean(dep_means),
            'control_flow': safe_mean(cf_means),
            'error_propagation': safe_mean(ep_means),
            'success_count': results.get('success', 0),
            'total_count': results.get('total', 0),
        }

    lines.append(
        f"{'Model':<35} {'Overall':>10} {'Order':>10} {'Dep':>10} {'CF':>10} {'EP':>10} {'Success':>10}"
    )
    lines.append("-" * 100)

    sorted_models = sorted(
        model_stats.items(),
        key=lambda x: x[1]['overall'] if x[1]['overall'] is not None else -1,
        reverse=True,
    )

    for model_name, stats in sorted_models:
        def fmt(val):
            return f"{val:.2%}" if val is not None else "N/A"

        success_rate = f"{stats['success_count']}/{stats['total_count']}"
        lines.append(
            f"{model_name:<35} "
            f"{fmt(stats['overall']):>10} "
            f"{fmt(stats['order']):>10} "
            f"{fmt(stats['dependency']):>10} "
            f"{fmt(stats['control_flow']):>10} "
            f"{fmt(stats['error_propagation']):>10} "
            f"{success_rate:>10}"
        )

    lines.extend([
        "",
        "=" * 100,
        "",
        "Legend:",
        "  Overall: Weighted overall score (Order*0.4 + Dep*0.2 + CF*0.0 + EP*0.4)",
        "  Order: Execution order accuracy",
        "  Dep: Dependency accuracy",
        "  CF: Control flow accuracy",
        "  EP: Error propagation score",
        "  Success: Successfully evaluated projects / Total",
        "",
        "=" * 100,
    ])
    return "\n".join(lines)


def _print_single_project_summary(result: Dict):
    print(f"\n{'='*60}")
    print("EVALUATION RESULTS SUMMARY")
    print(f"{'='*60}")

    status = result.get('status', 'unknown')
    if status == 'success':
        overall = result.get('overall_score', {})
        metrics = result.get('metrics', {})

        def fmt_score(score_dict):
            if not score_dict:
                return "N/A"
            mean = score_dict.get('mean')
            std = score_dict.get('std')
            if mean is None:
                return "N/A"
            if std and std > 0:
                return f"{mean:.2%} +/- {std:.2%}"
            return f"{mean:.2%}"

        print(f"\n  Status: SUCCESS")
        print(f"  Successful Runs: {result.get('successful_runs', '?')}/{result.get('total_runs', '?')}")
        print(f"\n  Scores (Mean +/- Std):")
        print(f"    Overall Score:       {fmt_score(overall)}")
        print(f"    Order Accuracy:      {fmt_score(metrics.get('order_accuracy', {}))}")
        print(f"    Dependency Accuracy: {fmt_score(metrics.get('dependency_accuracy', {}))}")
        print(f"    Control Flow:        {fmt_score(metrics.get('control_flow_accuracy', {}))}")
        print(f"    Error Propagation:   {fmt_score(metrics.get('error_propagation', {}))}")

        if isinstance(overall, dict) and overall.get('values'):
            print(f"\n  Individual Run Scores:")
            for i, score in enumerate(overall['values'], 1):
                print(f"    Run {i}: {score:.2%}")

    elif status == 'skipped':
        print(f"\n  Status: SKIPPED — {result.get('reason', 'Unknown')}")
    else:
        print(f"\n  Status: FAILED — {result.get('error', 'Unknown error')}")

    print(f"{'='*60}")



async def main():
    import argparse
    from utils.logger import setup_logger

    parser = argparse.ArgumentParser(
        description='Q2: Workflow Ordering Evaluation System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tasks/q2_workflow_ordering.py --config config_gpt51.yaml

  python tasks/q2_workflow_ordering.py --config config_gpt51.yaml --single -p 1

  python tasks/q2_workflow_ordering.py --config config_claude_haiku.yaml --runs 3 --output ./my_output

  python tasks/q2_workflow_ordering.py --config config_gpt51.yaml --force
        """,
    )
    parser.add_argument("--config", type=str, default="config.yaml", help="Config YAML file")
    parser.add_argument("--dataset", type=str, default=None, help="Dataset path (overrides config)")
    parser.add_argument("--output", type=str, default=None, help="Output directory (overrides config)")
    parser.add_argument("--runs", type=int, default=NUM_RUNS, help=f"Runs per project (default: {NUM_RUNS})")
    parser.add_argument("--force", action="store_true", help="Force re-run even if results exist")
    parser.add_argument("--single", action="store_true", help="Single project mode")
    parser.add_argument("-p", "--project", type=int, default=1, help="Project ID (for --single mode)")

    args = parser.parse_args()
    setup_logger()

    config = EvaluationConfig(args.config)
    llm_interface = LLMInterface(config.llm_config)

    reference_workflow_root_path = Path(args.dataset if args.dataset else config.dataset_path)
    output_root_dir = Path(args.output if args.output else config.output_path) / 'q2_workflow_ordering'
    output_root_dir.mkdir(exist_ok=True, parents=True)

    model_name = config.llm_config.model_name

    if args.single:
        print("=" * 80)
        print("Q2: Workflow Ordering — Single Project Mode")
        print(f"Model: {model_name}  |  Project: {args.project}  |  Runs: {args.runs}")
        print("=" * 80)

        project_path = reference_workflow_root_path / f'mcp_project{args.project}'
        if not project_path.exists():
            project_path = reference_workflow_root_path / f'mcp_project{args.project:02d}'
        if not project_path.exists():
            print(f"\n  Error: Project directory not found: {reference_workflow_root_path / f'mcp_project{args.project}'}")
            return

        project_output_dir = output_root_dir / model_name / str(args.project)
        project_output_dir.mkdir(parents=True, exist_ok=True)

        aggregated_path = project_output_dir / 'aggregated_results.json'
        if not args.force and aggregated_path.exists():
            print(f"\n  Found existing results at: {aggregated_path}")
            with open(aggregated_path, 'r', encoding='utf-8') as f:
                result = json.load(f)
            _print_single_project_summary(result)
            return

        log_file_path = project_output_dir / 'execution_log.txt'
        try:
            with DualLogger(log_file_path):
                result = await evaluate_single_project(
                    project_num=args.project,
                    project_path=project_path,
                    llm_interface=llm_interface,
                    project_output_dir=project_output_dir,
                    num_runs=args.runs,
                )
                result['project_num'] = args.project
                result['model_name'] = model_name

                with open(project_output_dir / 'final_results.json', 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                _print_single_project_summary(result)
        except Exception as e:
            print(f"\n  FATAL ERROR: {e}")
            traceback.print_exc()
        return

    print("=" * 80)
    print("Q2: Workflow Ordering — Batch Mode")
    print(f"Model: {model_name}  |  Runs per project: {args.runs}")
    print("=" * 80)

    mcp_projects = []
    for item in reference_workflow_root_path.iterdir():
        if item.is_dir() and item.name.startswith('mcp_project'):
            try:
                project_num = int(item.name.replace('mcp_project', ''))
                mcp_projects.append((project_num, item))
            except ValueError:
                continue
    mcp_projects.sort(key=lambda x: x[0])
    print(f"\n  Found {len(mcp_projects)} mcp_project directories")

    model_results = await evaluate_model(
        model_name=model_name,
        llm_interface=llm_interface,
        mcp_projects=mcp_projects,
        output_root_dir=output_root_dir,
        num_runs=args.runs,
        force_rerun=args.force,
    )

    summary_report = generate_summary_report(model_results)
    print("\n" + summary_report)

    print(f"\n  Results saved to: {output_root_dir.absolute()}")


if __name__ == '__main__':
    asyncio.run(main())
