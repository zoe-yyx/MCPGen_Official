"""
=====================================



   from utils.error_propagation import calculate_error_propagation

   results['metrics']['error_propagation'] = self._evaluate_error_propagation(gen_steps)



"""

from typing import Dict, List, Set, Tuple
from collections import defaultdict, deque



def build_dependency_graph(dependencies: Dict[str, List[str]]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """
    
    Args:
    
    Returns:
    """
    forward_graph = defaultdict(set)
    backward_graph = defaultdict(set)
    all_nodes = set()
    
    for parent, children in dependencies.items():
        all_nodes.add(parent)
        for child in children:
            all_nodes.add(child)
            forward_graph[parent].add(child)
            backward_graph[child].add(parent)
    
    for node in all_nodes:
        if node not in forward_graph:
            forward_graph[node] = set()
        if node not in backward_graph:
            backward_graph[node] = set()
    
    return dict(forward_graph), dict(backward_graph)


def get_all_descendants(node: str, forward_graph: Dict[str, Set[str]]) -> Set[str]:
    descendants = set()
    queue = deque([node])
    visited = {node}
    
    while queue:
        current = queue.popleft()
        for child in forward_graph.get(current, []):
            if child not in visited:
                visited.add(child)
                descendants.add(child)
                queue.append(child)
    
    return descendants


def get_longest_path_from_node(node: str, forward_graph: Dict[str, Set[str]]) -> int:
    memo = {}
    in_progress = set()

    def dfs(n: str) -> int:
        if n in memo:
            return memo[n]
        if n in in_progress:
            # cycle detected — treat as path length 0 to break recursion
            return 0
        in_progress.add(n)

        children = forward_graph.get(n, set())
        if not children:
            memo[n] = 0
            in_progress.discard(n)
            return 0

        max_child_path = max((dfs(child) for child in children), default=0)
        memo[n] = 1 + max_child_path
        in_progress.discard(n)
        return memo[n]

    return dfs(node)


def identify_error_nodes(
    ref_order: List[str],
    gen_order: List[str],
    ref_deps: Dict[str, List[str]],
    gen_deps: Dict[str, List[str]]
) -> Dict[str, Dict]:
    """
    
    """
    error_nodes = {}
    
    ref_set = set(ref_order)
    gen_set = set(gen_order)
    
    for node in (ref_set - gen_set):
        error_nodes[node] = {
            'error_type': 'missing',
            'severity': 1.0,
            'details': 'Node missing in generated workflow'
        }
    
    for node in (gen_set - ref_set):
        error_nodes[node] = {
            'error_type': 'extra',
            'severity': 0.5,
            'details': 'Node not in reference workflow'
        }
    
    common_nodes = ref_set & gen_set
    ref_pos = {node: i for i, node in enumerate(ref_order)}
    gen_pos = {node: i for i, node in enumerate(gen_order)}
    
    for node in common_nodes:
        errors = []
        
        ref_p, gen_p = ref_pos.get(node, -1), gen_pos.get(node, -1)
        if ref_p != gen_p:
            position_shift = abs(ref_p - gen_p) / len(ref_order)
            errors.append({
                'type': 'position',
                'ref_position': ref_p,
                'gen_position': gen_p,
                'shift': position_shift
            })
        
        ref_next = set(ref_deps.get(node, []))
        gen_next = set(gen_deps.get(node, []))
        
        if ref_next != gen_next:
            missing_deps = ref_next - gen_next
            extra_deps = gen_next - ref_next
            dep_error_rate = len(missing_deps | extra_deps) / max(len(ref_next), 1)
            errors.append({
                'type': 'dependency',
                'missing_deps': list(missing_deps),
                'extra_deps': list(extra_deps),
                'error_rate': dep_error_rate
            })
        
        if errors:
            severity = sum(
                e['shift'] * 0.3 if e['type'] == 'position' else e['error_rate'] * 0.7
                for e in errors
            )
            error_nodes[node] = {
                'error_type': 'order_or_dependency',
                'severity': min(severity, 1.0),
                'details': errors
            }
    
    return error_nodes


def calculate_error_propagation(
    ref_order: List[str],
    gen_order: List[str],
    ref_deps: Dict[str, List[str]],
    gen_steps: List[Dict]
) -> Dict:
    """
    
    """
    gen_deps = {
        step['step_id']: step['next_steps']
        for step in gen_steps if step.get('next_steps')
    }
    
    forward_graph, _ = build_dependency_graph(ref_deps)
    
    error_nodes = identify_error_nodes(ref_order, gen_order, ref_deps, gen_deps)
    
    if not error_nodes:
        return {
            'score': 1.0,
            'error_propagation_rate': 0.0,
            'propagation_depth': 0,
            'propagation_breadth': 0.0,
            'weighted_impact': 0.0,
            'error_nodes_count': 0,
            'affected_nodes_count': 0,
            'total_nodes': len(ref_order),
            'details': {'error_nodes': {}, 'propagation_chains': []}
        }
    
    total_nodes = len(ref_order)
    ref_pos = {node: i for i, node in enumerate(ref_order)}
    
    propagation_chains = []
    total_weighted_impact = 0.0
    max_propagation_depth = 0
    all_affected_nodes = set()
    
    for error_node, error_info in error_nodes.items():
        if error_node not in forward_graph:
            continue
        
        descendants = get_all_descendants(error_node, forward_graph)
        all_affected_nodes.update(descendants)
        
        propagation_depth = get_longest_path_from_node(error_node, forward_graph)
        max_propagation_depth = max(max_propagation_depth, propagation_depth)
        
        node_position = ref_pos.get(error_node, total_nodes - 1)
        position_weight = 1 - (node_position / total_nodes)
        
        breadth_impact = len(descendants) / total_nodes if total_nodes > 0 else 0
        depth_impact = propagation_depth / total_nodes if total_nodes > 0 else 0
        
        weighted_impact = error_info['severity'] * position_weight * (0.6 * breadth_impact + 0.4 * depth_impact)
        total_weighted_impact += weighted_impact
        
        propagation_chains.append({
            'error_node': error_node,
            'error_type': error_info['error_type'],
            'severity': error_info['severity'],
            'position': node_position,
            'position_weight': position_weight,
            'descendants': list(descendants),
            'descendant_count': len(descendants),
            'propagation_depth': propagation_depth,
            'breadth_impact': breadth_impact,
            'depth_impact': depth_impact,
            'weighted_impact': weighted_impact
        })
    
    propagation_breadth = len(all_affected_nodes) / total_nodes if total_nodes > 0 else 0
    normalized_impact = total_weighted_impact / len(error_nodes) if error_nodes else 0
    error_propagation_rate = min(1.0, propagation_breadth * 0.5 + normalized_impact * 0.5)
    score = 1.0 - error_propagation_rate
    
    return {
        'score': score,
        'error_propagation_rate': error_propagation_rate,
        'propagation_depth': max_propagation_depth,
        'propagation_breadth': propagation_breadth,
        'weighted_impact': normalized_impact,
        'error_nodes_count': len(error_nodes),
        'affected_nodes_count': len(all_affected_nodes),
        'total_nodes': total_nodes,
        'details': {
            'error_nodes': error_nodes,
            'propagation_chains': propagation_chains
        }
    }


"""


    def evaluate(self, generated_workflow: Dict) -> Dict:
        gen_steps = generated_workflow['workflow_steps']
        gen_order = [s['step_id'] for s in gen_steps]
        
        self.generated_workflow_steps = gen_steps
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'reference_order': self.reference_answer['execution_order'],
            'generated_order': gen_order,
            'metrics': {}
        }
        
        results['metrics']['order_accuracy'] = self._evaluate_order(gen_order)
        
        results['metrics']['dependency_accuracy'] = self._evaluate_dependencies(gen_steps)
        
        results['metrics']['control_flow_accuracy'] = self._evaluate_control_flow(gen_steps)
        
        results['metrics']['error_propagation'] = self._evaluate_error_propagation(gen_steps)
        
        results['overall_score'] = self._calculate_overall_score(results['metrics'])
        
        return results



    def _evaluate_error_propagation(self, gen_steps: List[Dict]) -> Dict:
        from utils.error_propagation import calculate_error_propagation
        
        return calculate_error_propagation(
            ref_order=self.reference_answer['execution_order'],
            gen_order=[s['step_id'] for s in gen_steps],
            ref_deps=self.reference_answer['dependencies'],
            gen_steps=gen_steps
        )



    def _calculate_overall_score(self, metrics: Dict) -> float:
        order_metrics = metrics.get('order_accuracy', {})
        order_score = order_metrics.get('overall_path_correctness', 0.0)
        
        weights = {
        }
        
        total_score = (
            weights['order'] * order_score +
            weights['dependency_accuracy'] * metrics.get('dependency_accuracy', {}).get('score', 0.0) +
            weights['control_flow_accuracy'] * metrics.get('control_flow_accuracy', {}).get('score', 0.0) +
            weights['error_propagation'] * metrics.get('error_propagation', {}).get('score', 0.0)
        )
        
        return total_score
"""
