"""
tasks/comprehensive_metrics.py

"""
import ast
import importlib.util
import sys
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


@dataclass
class ComprehensiveToolMetrics:
    
    syntax_valid: bool = False
    syntax_errors: List[str] = field(default_factory=list)
    
    imports_valid: bool = False
    import_errors: List[str] = field(default_factory=list)
    missing_modules: List[str] = field(default_factory=list)
    
    has_target_function: bool = False
    target_function_name: Optional[str] = None
    
    has_docstring: bool = False
    docstring_quality_score: float = 0.0  # 0-1
    
    follows_naming_conventions: bool = False
    naming_violations: List[str] = field(default_factory=list)
    
    has_type_hints: bool = False
    
    no_dangerous_operations: bool = True
    dangerous_operations: List[str] = field(default_factory=list)
    
    signature_matches_original: bool = False
    param_count_correct: bool = False
    param_names_match: bool = False
    param_types_match: bool = False
    return_type_matches: bool = False
    
    original_signature: Optional[str] = None
    generated_signature: Optional[str] = None
    signature_diff: Optional[str] = None
    
    workflow_execution_success: bool = False
    execution_error_message: Optional[str] = None
    execution_time: float = 0.0
    
    output_format_correct: bool = False
    output_validation_passed: bool = False
    
    test_stdout: Optional[str] = None
    test_stderr: Optional[str] = None
    
    
    warnings: List[str] = field(default_factory=list)
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_overall_score(self) -> float:
        """
        
        """
        weights = {
            'syntax_valid': 0.10,
            'imports_valid': 0.08,
            'has_target_function': 0.12,
            'signature_matches_original': 0.25,
            'workflow_execution_success': 0.30,
            'has_docstring': 0.03,
            'has_type_hints': 0.05,
            'follows_naming_conventions': 0.02,
            'no_dangerous_operations': 0.05,
        }
        
        score = 0.0
        for metric, weight in weights.items():
            value = getattr(self, metric, False)
            if isinstance(value, bool):
                score += weight if value else 0
            elif isinstance(value, (int, float)):
                score += weight * min(1.0, max(0.0, value))
        
        return score
    
    def get_category_scores(self) -> Dict[str, float]:
        return {
            'code_quality': self._calc_code_quality_score(),
            'signature_matching': self._calc_signature_score(),
            'functional_correctness': self._calc_functional_score(),
            'code_standards': self._calc_standards_score(),
        }
    
    def _calc_code_quality_score(self) -> float:
        score = 0.0
        if self.syntax_valid: score += 0.3
        if self.imports_valid: score += 0.25
        if self.has_target_function: score += 0.35
        if self.no_dangerous_operations: score += 0.1
        return score
    
    def _calc_signature_score(self) -> float:
        if not self.has_target_function:
            return 0.0
        score = 0.0
        if self.param_count_correct: score += 0.4
        if self.param_names_match: score += 0.3
        if self.param_types_match: score += 0.2
        if self.return_type_matches: score += 0.1
        return score
    
    def _calc_functional_score(self) -> float:
        score = 0.0
        if self.workflow_execution_success: score += 0.7
        if self.output_format_correct: score += 0.15
        if self.output_validation_passed: score += 0.15
        return score
    
    def _calc_standards_score(self) -> float:
        score = 0.0
        if self.has_docstring: score += 0.3
        if self.has_type_hints: score += 0.4
        if self.follows_naming_conventions: score += 0.3
        return score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'overall_score': self.get_overall_score(),
            'category_scores': self.get_category_scores(),
            
            'code_quality': {
                'syntax_valid': self.syntax_valid,
                'syntax_errors': self.syntax_errors,
                'imports_valid': self.imports_valid,
                'import_errors': self.import_errors,
                'missing_modules': self.missing_modules,
                'has_target_function': self.has_target_function,
                'has_docstring': self.has_docstring,
                'docstring_quality_score': self.docstring_quality_score,
                'has_type_hints': self.has_type_hints,
                'type_coverage': self.type_coverage,
                'follows_naming_conventions': self.follows_naming_conventions,
                'naming_violations': self.naming_violations,
                'no_dangerous_operations': self.no_dangerous_operations,
                'dangerous_operations': self.dangerous_operations,
            },
            
            'signature_matching': {
                'matches_original': self.signature_matches_original,
                'param_count_correct': self.param_count_correct,
                'param_names_match': self.param_names_match,
                'param_types_match': self.param_types_match,
                'return_type_matches': self.return_type_matches,
                'original_signature': self.original_signature,
                'generated_signature': self.generated_signature,
                'signature_diff': self.signature_diff,
            },
            
            'functional_correctness': {
                'workflow_execution_success': self.workflow_execution_success,
                'execution_error_message': self.execution_error_message,
                'execution_time': self.execution_time,
                'output_format_correct': self.output_format_correct,
                'output_validation_passed': self.output_validation_passed,
            },
            
            'similarity': {
                'code_similarity_score': self.code_similarity_score,
                'structural_similarity': self.structural_similarity,
            },
            
            'warnings': self.warnings,
            'metadata': self.analysis_metadata,
        }


class ComprehensiveMetricsAnalyzer:

    def __init__(self, original_tool_path: Optional[Path] = None):
        self.original_tool_path = original_tool_path
        self.original_tool_info = None
    
    def analyze(
        self,
        generated_code: str,
        tool_name: str,
        execution_result: Optional[Dict[str, Any]] = None
    ) -> ComprehensiveToolMetrics:
        """

        Args:

        Returns:
            ComprehensiveToolMetrics
        """
        metrics = ComprehensiveToolMetrics()
        metrics.target_function_name = tool_name

        if self.original_tool_path and self.original_tool_path.exists() and not self.original_tool_info:
            self.original_tool_info = self._extract_original_info(tool_name)

        self._check_syntax(generated_code, metrics)
        if not metrics.syntax_valid:
            return metrics

        try:
            tree = ast.parse(generated_code)

            self._check_imports(tree, metrics)

            func_node = self._find_function(tree, tool_name)

            if func_node:
                metrics.has_target_function = True

                self._check_docstring(func_node, metrics)

                self._check_type_hints(func_node, metrics)

                self._check_naming_conventions(func_node, metrics)

                if self.original_tool_info:
                    self._compare_signatures(func_node, metrics)
            else:
                metrics.syntax_errors.append(f"Function '{tool_name}' not found")
            
            self._check_dangerous_operations(tree, metrics)
            
        except Exception as e:
            metrics.syntax_errors.append(f"AST analysis failed: {str(e)}")
            return metrics
        
        if self.original_tool_path and self.original_tool_path.exists():
            self._calculate_similarity(generated_code, metrics)
        
        if execution_result:
            self._analyze_execution(execution_result, metrics)
        
        return metrics
    
    def _check_syntax(self, code: str, metrics: ComprehensiveToolMetrics):
        try:
            compile(code, "<string>", "exec")
            metrics.syntax_valid = True
        except SyntaxError as e:
            metrics.syntax_valid = False
            metrics.syntax_errors.append(
                f"Line {e.lineno}: {e.msg}"
            )
        except Exception as e:
            metrics.syntax_valid = False
            metrics.syntax_errors.append(f"Compilation error: {str(e)}")
    
    def _check_imports(self, tree: ast.AST, metrics: ComprehensiveToolMetrics):
        all_imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    all_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    all_imports.append(node.module)
        
        missing = []
        for module_name in all_imports:
            if not self._is_module_available(module_name):
                missing.append(module_name)
                metrics.import_errors.append(f"Module '{module_name}' not available")
        
        metrics.missing_modules = missing
        metrics.imports_valid = len(missing) == 0
    
    def _is_module_available(self, module_name: str) -> bool:
        base_module = module_name.split('.')[0]
        
        try:
            if hasattr(sys, 'stdlib_module_names') and base_module in sys.stdlib_module_names:
                return True
            
            spec = importlib.util.find_spec(base_module)
            return spec is not None
        except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
            return False
    
    def _find_function(self, tree: ast.AST, function_name: str) -> Optional[ast.FunctionDef]:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    return node
        
        normalized_search = function_name.replace('_tool', '').replace('_', '').lower()
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                normalized_func = node.name.replace('_tool', '').replace('_', '').lower()
                if normalized_func == normalized_search:
                    logger.warning(
                        f"Found function with different name: "
                        f"expected '{function_name}', got '{node.name}'"
                    )
                    return node
        return None
    
    def _check_docstring(self, func: ast.FunctionDef, metrics: ComprehensiveToolMetrics):
        docstring = ast.get_docstring(func)
        metrics.has_docstring = docstring is not None
        
        if docstring:
            score = 0.0
            metrics.docstring_quality_score = min(1.0, score)
        else:
            metrics.warnings.append("Missing docstring")
    
    def _check_type_hints(self, func: ast.FunctionDef, metrics: ComprehensiveToolMetrics):
        total_params = len(func.args.args)
        typed_params = sum(1 for arg in func.args.args if arg.annotation is not None)
        
        metrics.has_type_hints = typed_params > 0
        metrics.type_coverage = typed_params / total_params if total_params > 0 else 0.0
        
        if typed_params < total_params:
            metrics.warnings.append(
                f"Only {typed_params}/{total_params} parameters have type hints"
            )
        
        if func.returns is None:
            metrics.warnings.append("Missing return type hint")
    
    def _check_naming_conventions(self, func: ast.FunctionDef, metrics: ComprehensiveToolMetrics):
        violations = []
        
        if not func.name.islower():
            violations.append(f"Function name '{func.name}' should be lowercase")
        
        if func.name.startswith('_') and not func.name.startswith('__'):
            violations.append(f"Tool function should not start with '_'")
        
        for arg in func.args.args:
            if not arg.arg.islower() or arg.arg.startswith('_'):
                violations.append(f"Parameter '{arg.arg}' should be lowercase")
        
        metrics.naming_violations = violations
        metrics.follows_naming_conventions = len(violations) == 0
    
    def _check_dangerous_operations(self, tree: ast.AST, metrics: ComprehensiveToolMetrics):
        dangerous_funcs = {'eval', 'exec', 'compile', '__import__', 'open'}
        dangerous_found = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in dangerous_funcs:
                        dangerous_found.append(node.func.id)
        
        metrics.dangerous_operations = list(set(dangerous_found))
        metrics.no_dangerous_operations = len(dangerous_found) == 0
        
        if dangerous_found:
            metrics.warnings.append(
                f"Dangerous operations found: {', '.join(set(dangerous_found))}"
            )
    
    def _compare_signatures(self, func: ast.FunctionDef, metrics: ComprehensiveToolMetrics):
        if not self.original_tool_info:
            return

        original = self.original_tool_info

        gen_params_info = self._extract_params_info(func)
        gen_params = [p['name'] for p in gen_params_info]

        orig_params = original.get('parameters', [])
        orig_params_info = original.get('params_info', [])

        metrics.param_count_correct = len(gen_params) == len(orig_params)

        metrics.param_names_match = gen_params == orig_params

        defaults_match = True
        default_issues = []

        if metrics.param_names_match and orig_params_info:
            for orig_p, gen_p in zip(orig_params_info, gen_params_info):
                if orig_p.get('has_default') and not gen_p.get('has_default'):
                    defaults_match = False
                    default_issues.append(
                        f"Parameter '{orig_p['name']}' should have default value"
                    )

        types_match = True
        if orig_params_info and gen_params_info and len(orig_params_info) == len(gen_params_info):
            for orig_p, gen_p in zip(orig_params_info, gen_params_info):
                if orig_p.get('type_annotation') and not gen_p.get('type_annotation'):
                    types_match = False
                    break

        metrics.param_types_match = types_match
        metrics.return_type_matches = func.returns is not None if original.get('has_return_type') else True

        metrics.signature_matches_original = (
            metrics.param_count_correct and
            metrics.param_names_match and
            defaults_match
        )

        def format_param(p_info):
            s = p_info['name']
            if p_info.get('type_annotation'):
                s += f": {p_info['type_annotation']}"
            if p_info.get('has_default'):
                s += " = ..." if not p_info.get('default_is_none') else " = None"
            return s

        orig_sig_parts = [format_param(p) for p in orig_params_info] if orig_params_info else orig_params
        gen_sig_parts = [format_param(p) for p in gen_params_info]

        metrics.original_signature = f"{original.get('name')}({', '.join(orig_sig_parts)})"
        metrics.generated_signature = f"{func.name}({', '.join(gen_sig_parts)})"

        if not metrics.signature_matches_original:
            diff_parts = []
            if not metrics.param_count_correct:
                diff_parts.append(f"Parameter count: expected {len(orig_params)}, got {len(gen_params)}")
            if not metrics.param_names_match:
                diff_parts.append(f"Parameter names mismatch")
            if default_issues:
                diff_parts.extend(default_issues)

            metrics.signature_diff = (
                f"Expected: {metrics.original_signature}\n"
                f"Got: {metrics.generated_signature}\n"
                f"Issues: {'; '.join(diff_parts)}"
            )
    
    def _calculate_similarity(self, generated_code: str, metrics: ComprehensiveToolMetrics):
        try:
            with open(self.original_tool_path, 'r', encoding='utf-8') as f:
                original_code = f.read()
            
            matcher = difflib.SequenceMatcher(None, original_code, generated_code)
            metrics.code_similarity_score = matcher.ratio()
            
            metrics.structural_similarity = 0.0
            
        except Exception as e:
            logger.warning(f"Failed to calculate similarity: {e}")
    
    def _analyze_execution(self, execution_result: Dict[str, Any], metrics: ComprehensiveToolMetrics):
        metrics.workflow_execution_success = execution_result.get('success', False)
        metrics.execution_time = execution_result.get('execution_time', 0.0)
        metrics.execution_error_message = execution_result.get('error')
        metrics.test_stdout = execution_result.get('stdout')
        metrics.test_stderr = execution_result.get('stderr')
        
        if metrics.workflow_execution_success:
            metrics.output_format_correct = True
            metrics.output_validation_passed = True
        else:
            if metrics.test_stderr:
                stderr = metrics.test_stderr.lower()
                if 'importerror' in stderr or 'modulenotfounderror' in stderr:
                    metrics.warnings.append("Import error during execution")
                elif 'syntaxerror' in stderr:
                    metrics.warnings.append("Syntax error during execution")
                elif 'typeerror' in stderr:
                    metrics.warnings.append("Type error during execution")
    
    def _extract_original_info(self, tool_name: str) -> Dict[str, Any]:
        """

        Args:
        """
        try:
            with open(self.original_tool_path, 'r', encoding='utf-8') as f:
                code = f.read()

            tree = ast.parse(code)
            func_node = self._find_function(tree, tool_name)

            if not func_node:
                logger.warning(f"Function '{tool_name}' not found in {self.original_tool_path}")
                return {}

            params_info = self._extract_params_info(func_node)

            return {
                'name': tool_name,
                'parameters': [p['name'] for p in params_info],
                'has_return_type': func_node.returns is not None,
                'docstring': ast.get_docstring(func_node),
            }
        except Exception as e:
            logger.warning(f"Failed to extract original tool info for '{tool_name}': {e}")
            return {}

    def _extract_params_info(self, func_node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """

        Args:

        Returns:
        """
        params_info = []
        args = func_node.args

        num_defaults = len(args.defaults)
        num_args = len(args.args)
        first_default_idx = num_args - num_defaults

        for i, arg in enumerate(args.args):
            param_info = {
                'name': arg.arg,
                'has_default': i >= first_default_idx,
                'default_is_none': False,
                'type_annotation': ast.unparse(arg.annotation) if arg.annotation else None,
            }

            if i >= first_default_idx:
                default_idx = i - first_default_idx
                default_node = args.defaults[default_idx]
                if isinstance(default_node, ast.Constant) and default_node.value is None:
                    param_info['default_is_none'] = True

            params_info.append(param_info)

        return params_info
