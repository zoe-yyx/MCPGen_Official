"""
tasks/mcp_tool_regenerator.py 
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List

from core.config import EvaluationConfig
from utils.llm_interface import LLMInterface
from utils.comprehensive_metrics import ComprehensiveToolMetrics, ComprehensiveMetricsAnalyzer
from utils.isolated_test_env import IsolatedTestEnvironment, TestRunner
from utils.improved_prompts import ImprovedPromptBuilder
from utils.project_commands import ProjectCommandManager

logger = logging.getLogger(__name__)

# Per-project time budget constants
PROJECT_TIME_BUDGET = 1800  # 30 minutes max per project
BASELINE_FAIL_TIMEOUT = 60  # Reduced timeout for projects with broken baselines


@dataclass
class IndividualTestResult:
    tool_name: str
    success: bool
    execution_time: float = 0.0
    error_message: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'tool_name': self.tool_name,
            'success': self.success,
            'execution_time': self.execution_time,
            'error_message': self.error_message,
        }


@dataclass 
class CollectiveTestResult:
    success: bool
    execution_time: float = 0.0
    error_message: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    tools_tested: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'execution_time': self.execution_time,
            'error_message': self.error_message,
            'tools_tested': self.tools_tested,
        }


@dataclass
class RegeneratedTool:
    
    name: str
    code: str
    
    original_path: Optional[Path] = None
    generated_path: Optional[Path] = None
    
    static_metrics: Optional[ComprehensiveToolMetrics] = None
    
    individual_test: Optional[IndividualTestResult] = None
    
    generation_time: float = 0.0
    prompt_used: Optional[str] = None
    
    @property
    def individual_test_success(self) -> bool:
        return self.individual_test.success if self.individual_test else False
    
    @property
    def static_analysis_passed(self) -> bool:
        if not self.static_metrics:
            return False
        return self.static_metrics.syntax_valid and self.static_metrics.has_target_function
    
    def to_dict(self, include_code: bool = False, include_prompt: bool = False) -> Dict[str, Any]:
        result = {
            'name': self.name,
            'original_path': str(self.original_path) if self.original_path else None,
            'generated_path': str(self.generated_path) if self.generated_path else None,
            'generation_time': self.generation_time,
            'static_analysis_passed': self.static_analysis_passed,
            'individual_test_success': self.individual_test_success,
        }
        
        if include_code:
            result['code'] = self.code
        if include_prompt:
            result['prompt_used'] = self.prompt_used
        if self.static_metrics:
            result['static_metrics'] = self.static_metrics.to_dict()
        if self.individual_test:
            result['individual_test'] = self.individual_test.to_dict()
        
        return result


@dataclass
class RegenerationResult:
    
    workflow_id: str
    workflow_name: str
    tools: List[RegeneratedTool] = field(default_factory=list)
    
    total_tools: int = 0
    static_analysis_passed: int = 0
    
    
    collective_test: Optional[CollectiveTestResult] = None
    
    high_quality_tools: int = 0  # static_passed AND individual_passed AND collective_passed

    baseline_error: Optional[str] = None

    project_classification: Optional[Dict[str, Any]] = None

    total_time: float = 0.0
    average_generation_time: float = 0.0

    error_message: Optional[str] = None
    
    @property
    def collective_test_success(self) -> bool:
        return self.collective_test.success if self.collective_test else False
    
    @property
    def all_individual_tests_passed(self) -> bool:
        return self.individual_test_passed == self.total_tools and self.total_tools > 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            
            'total_tools': self.total_tools,
            'static_analysis_passed': self.static_analysis_passed,
            'static_pass_rate': self.static_analysis_passed / self.total_tools if self.total_tools > 0 else 0.0,
            
            'individual_test': {
                'passed': self.individual_test_passed,
                'pass_rate': self.individual_test_passed / self.total_tools if self.total_tools > 0 else 0.0,
                'all_passed': self.all_individual_tests_passed,
            },
            
            'collective_test': self.collective_test.to_dict() if self.collective_test else None,
            
            'high_quality_tools': self.high_quality_tools,
            'high_quality_rate': self.high_quality_tools / self.total_tools if self.total_tools > 0 else 0.0,

            # Baseline
            'baseline_success': self.baseline_success,
            'baseline_error': self.baseline_error,

            'project_classification': self.project_classification,

            'total_time': self.total_time,
            'average_generation_time': self.average_generation_time,

            'error_message': self.error_message,
            'tools': [tool.to_dict() for tool in self.tools],
        }


class MCPToolRegenerator:

    def __init__(self, config: EvaluationConfig, llm_interface: LLMInterface):
        self.config = config
        self.llm = llm_interface

        verification_results_path = Path("/hdd/yxyang/MCPFLow/mcp_projects/_reports/project_verification_results.json")
        self.command_manager = None
        if verification_results_path.exists():
            self.command_manager = ProjectCommandManager(verification_results_path)
            logger.info(f"Loaded project commands from {verification_results_path}")
        else:
            logger.warning(f"Project verification results not found at {verification_results_path}")
    
    async def regenerate_tool(
        self,
        workflow_dir: Path,
        tool_name: str,
        original_tool_path: Optional[Path] = None
    ) -> RegeneratedTool:
        start_time = time.time()
        
        tool = RegeneratedTool(
            name=tool_name,
            code="",
            original_path=original_tool_path
        )
        
        try:
            prompt_builder = ImprovedPromptBuilder(workflow_dir)
            prompt = prompt_builder.build_tool_generation_prompt(
                tool_name=tool_name,
                original_tool_path=original_tool_path,
                include_examples=True
            )
            tool.prompt_used = prompt
            
            logger.info(f"Generating code for tool: {tool_name}")
            raw_code = await self._generate_code(prompt)
            
            tool.code = self._clean_generated_code(raw_code)
            tool.generation_time = time.time() - start_time
            logger.info(f"Generated tool '{tool_name}' in {tool.generation_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to generate tool '{tool_name}': {e}")
            tool.generation_time = time.time() - start_time
        
        return tool
    
    async def _generate_code(self, prompt: str) -> str:
        system_message = (
            "You are an expert Python developer specializing in FastMCP tool development. "
            "Generate clean, production-quality code that follows all requirements exactly. "
            "Output ONLY the function code, no markdown, no explanations."
        )
        
        response = await self.llm.generate_response(
            prompt=prompt,
            system_message=system_message,
            temperature=0.2,
            max_tokens=2000,
        )
        
        return response if response else ""
    
    def _clean_generated_code(self, raw_code: str) -> str:
        import ast
        
        code = raw_code.strip()
        
        code = re.sub(r'^```(?:python)?\s*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n```\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'@mcp\.tool\(\)\s*\n', '', code)
        
        try:
            tree = ast.parse(code)
            has_class = any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
            
            if not has_class:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.args.args and node.args.args[0].arg == 'self':
                            func_lines = code.split('\n')
                            func_start = node.lineno - 1
                            
                            def_line = func_lines[func_start]
                            def_line = re.sub(r'\(self,\s*', '(', def_line)
                            def_line = re.sub(r'\(self\)', '()', def_line)
                            func_lines[func_start] = def_line
                            code = '\n'.join(func_lines)
                            break
        except (SyntaxError, ValueError):
            code = re.sub(r'def\s+(\w+)\s*\(\s*self,\s*', r'def \1(', code)
            code = re.sub(r'async\s+def\s+(\w+)\s*\(\s*self,\s*', r'async def \1(', code)
            code = re.sub(r'def\s+(\w+)\s*\(\s*self\s*\)', r'def \1()', code)
            code = re.sub(r'async\s+def\s+(\w+)\s*\(\s*self\s*\)', r'async def \1()', code)
        
        lines = code.split('\n')
        cleaned_lines = []
        prev_blank = False
        
        for line in lines:
            is_blank = line.strip() == ''
            if is_blank and prev_blank:
                continue
            cleaned_lines.append(line)
            prev_blank = is_blank
        
        return '\n'.join(cleaned_lines).strip()
    
    def _perform_static_analysis(self, tool: RegeneratedTool) -> ComprehensiveToolMetrics:
        analyzer = ComprehensiveMetricsAnalyzer(
            original_tool_path=tool.original_path
        )
        print(f"Performing static analysis for tool: {tool.name}")
        print("tool.original_path", tool.original_path)
        
        metrics = analyzer.analyze(
            generated_code=tool.code,
            tool_name=tool.name,
            execution_result=None
        )
        return metrics
    
    async def _run_individual_test(
        self,
        workflow_dir: Path,
        tool: RegeneratedTool
    ) -> IndividualTestResult:
        """
        
        """
        logger.info(f"[Individual Test] Testing tool: {tool.name}")
        
        result = IndividualTestResult(tool_name=tool.name, success=False)
        
        if not tool.code:
            result.error_message = "No code generated"
            return result
        
        with IsolatedTestEnvironment(workflow_dir, keep_on_error=False, command_manager=self.command_manager) as env:
            try:
                env.install_regenerated_tool(tool.name, tool.code)
                
                exec_result = env.run_workflow_test(
                    timeout=self.config.e2e_config.execution_timeout
                )
                
                result.success = exec_result.get('success', False)
                result.execution_time = exec_result.get('execution_time', 0.0)
                result.error_message = exec_result.get('error')
                result.stdout = exec_result.get('stdout')
                result.stderr = exec_result.get('stderr')
                
            except Exception as e:
                logger.error(f"Individual test failed for '{tool.name}': {e}")
                result.error_message = str(e)
        
        status = "✅ PASS" if result.success else "❌ FAIL"
        logger.info(f"[Individual Test] {tool.name}: {status}")
        return result
    
    async def _run_collective_test(
        self,
        workflow_dir: Path,
        tools: List[RegeneratedTool]
    ) -> CollectiveTestResult:
        """
        
        """
        valid_tools = [t for t in tools if t.static_analysis_passed and t.code]
        
        logger.info(f"[Collective Test] Testing {len(valid_tools)}/{len(tools)} tools together")
        
        result = CollectiveTestResult(
            success=False,
            tools_tested=[t.name for t in valid_tools]
        )
        
        if not valid_tools:
            result.error_message = "No valid tools to test"
            return result
        
        with IsolatedTestEnvironment(workflow_dir, keep_on_error=False, command_manager=self.command_manager) as env:
            try:
                for tool in valid_tools:
                    env.install_regenerated_tool(tool.name, tool.code)
                    logger.debug(f"Installed tool: {tool.name}")
                
                exec_result = env.run_workflow_test(
                    timeout=self.config.e2e_config.execution_timeout
                )
                
                result.success = exec_result.get('success', False)
                result.execution_time = exec_result.get('execution_time', 0.0)
                result.error_message = exec_result.get('error')
                result.stdout = exec_result.get('stdout')
                result.stderr = exec_result.get('stderr')
                
            except Exception as e:
                logger.error(f"Collective test failed: {e}")
                result.error_message = str(e)
        
        status = "✅ PASS" if result.success else "❌ FAIL"
        logger.info(f"[Collective Test] {status}")
        return result
    
    async def run_regeneration_evaluation(
        self,
        workflow_dir: Path,
        output_dir: Path
    ) -> RegenerationResult:
        """
        
        
        Returns:
        """
        start_time = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== Starting regeneration evaluation for workflow: {workflow_dir.name} ===")
        workflow_info = self._load_workflow_info(workflow_dir)
        
        result = RegenerationResult(
            workflow_id=workflow_info['id'],
            workflow_name=workflow_info['name'],
        )
        print(f"Workflow: {workflow_info['name']} (ID: {workflow_info['id']})")
        tools_from_workflow = self._discover_tools(workflow_dir)

        tools_to_regenerate = []
        skipped_tools = []
        for tool_name in tools_from_workflow:
            original_path = self._find_original_tool(workflow_dir, tool_name)
            if original_path:
                tools_to_regenerate.append((tool_name, original_path))
            else:
                skipped_tools.append(tool_name)
                logger.warning(f"⚠️ Skipping tool '{tool_name}': not found in MCP server")

        if skipped_tools:
            logger.warning(f"Skipped {len(skipped_tools)} tools not found in server: {skipped_tools}")

        result.total_tools = len(tools_to_regenerate)

        if result.total_tools == 0:
            logger.warning(f"No tools found in workflow: {workflow_info['name']}")
            result.error_message = "No tools found in MCP server"
            result.total_time = time.time() - start_time
            return result

        logger.info(f"Found {result.total_tools} tools to regenerate (skipped {len(skipped_tools)} missing tools)")

        # ============================================================
        # ============================================================
        logger.info("=" * 60)
        logger.info("Phase 0: Baseline Test (original workflow)")
        logger.info("=" * 60)

        try:
            with IsolatedTestEnvironment(
                workflow_dir, keep_on_error=False, command_manager=self.command_manager
            ) as env:
                baseline_exec = env.run_workflow_test(
                    timeout=self.config.e2e_config.execution_timeout
                )
                result.baseline_success = baseline_exec.get('success', False)
                result.baseline_error = baseline_exec.get('error')
        except Exception as e:
            logger.error(f"Baseline test failed with exception: {e}")
            result.baseline_success = False
            result.baseline_error = str(e)

        if result.baseline_success:
            logger.info("Phase 0: Baseline PASSED - original workflow works")
        else:
            logger.warning(f"Phase 0: Baseline FAILED - {result.baseline_error}")
            logger.warning("Results will be flagged: original workflow is broken")
            # Reduce timeout for broken projects to avoid wasting time
            logger.info(f"Reducing test timeout from {self.config.e2e_config.execution_timeout}s to {BASELINE_FAIL_TIMEOUT}s for baseline-failed project")
            self.config.e2e_config.execution_timeout = min(
                self.config.e2e_config.execution_timeout, BASELINE_FAIL_TIMEOUT
            )

        result.project_classification = self._classify_project(workflow_dir, actual_tool_count=result.total_tools)
        result.project_classification['baseline_success'] = result.baseline_success
        logger.info(f"Project classification: {result.project_classification}")

        # ============================================================
        # ============================================================
        logger.info("=" * 60)
        logger.info("Phase 1: Tool Generation & Static Analysis")
        logger.info("=" * 60)

        for tool_name, original_path in tools_to_regenerate:
            tool = await self.regenerate_tool(
                workflow_dir=workflow_dir,
                tool_name=tool_name,
                original_tool_path=original_path
            )
            
            tool.generated_path = self._save_generated_code(
                output_dir, tool_name, tool.code
            )
            
            tool.static_metrics = self._perform_static_analysis(tool)
            
            if tool.static_analysis_passed:
                result.static_analysis_passed += 1
                logger.info(f"  {tool_name}: ✅ Static analysis passed")
            else:
                logger.info(f"  {tool_name}: ❌ Static analysis failed")
            
            result.tools.append(tool)

        # ============================================================
        # ============================================================
        
        tools_code = {}
        for tool in result.tools:
            if tool.static_analysis_passed and tool.code:
                tools_code[tool.name] = tool.code
        
        test_runner = TestRunner(
            workflow_dir=workflow_dir,
            timeout=self.config.e2e_config.execution_timeout,
        )
        
        print("\n=== Running Tests ===",tools_code)
        test_results = test_runner.run_all_tests(tools_code, project_time_budget=PROJECT_TIME_BUDGET)
        
        print("\n=== Test Results Summary ===")

        print(f"Individual Test Results:", test_results)
        
        logger.info("=" * 60)
        logger.info("Phase 2: Individual Tool Tests (Results)")
        logger.info("=" * 60)
        
        for tool in result.tools:
            if tool.name in test_results['individual_results']:
                indiv_result = test_results['individual_results'][tool.name]
                print(f"Tool: {tool.name}, Result: {indiv_result}")

                tool.individual_test = IndividualTestResult(
                    tool_name=tool.name,
                    success=indiv_result.get('success', False),
                    execution_time=indiv_result.get('execution_time', 0),
                    error_message=indiv_result.get('error'),
                    stdout=indiv_result.get('stdout'),
                    stderr=indiv_result.get('stderr'),
                )
                if tool.individual_test.success:
                    result.individual_test_passed += 1
            else:
                tool.individual_test = IndividualTestResult(
                    tool_name=tool.name,
                    success=False,
                    error_message="Skipped: static analysis failed"
                )
        
        logger.info("=" * 60)
        logger.info("Phase 3: Collective Workflow Test (Results)")
        logger.info("=" * 60)

        coll_result = test_results.get('collective_result')
        if coll_result is not None:
            result.collective_test = CollectiveTestResult(
                success=coll_result.get('success', False),
                execution_time=coll_result.get('execution_time', 0),
                error_message=coll_result.get('error'),
                stdout=coll_result.get('stdout'),
                stderr=coll_result.get('stderr'),
                tools_tested=coll_result.get('tools_installed', []),
            )
        else:
            # No valid tools to test collectively
            result.collective_test = CollectiveTestResult(
                success=False,
                error_message="No valid tools to test (all failed static analysis)",
                tools_tested=[],
            )
        
        # ============================================================
        # ============================================================
        collective_passed = (result.collective_test is not None and result.collective_test.success)
        for tool in result.tools:
            if tool.static_analysis_passed and tool.individual_test_success and collective_passed:
                result.high_quality_tools += 1
        
        # ============================================================
        # ============================================================
        for tool in result.tools:
            self._save_tool_evaluation(output_dir, tool)
        
        result.total_time = time.time() - start_time
        if result.total_tools > 0:
            result.average_generation_time = sum(
                t.generation_time for t in result.tools
            ) / result.total_tools
        
        self._save_workflow_result(output_dir, result)
        
        self._print_result_summary(result)
        
        return result
    
    def _print_result_summary(self, result: RegenerationResult):
        print("\n" + "=" * 70)
        print(f"EVALUATION RESULT: {result.workflow_name}")
        print("=" * 70)
        
        print(f"\n📊 Tool Statistics:")
        print(f"   Total tools: {result.total_tools}")
        print(f"   Static analysis passed: {result.static_analysis_passed}/{result.total_tools} "
              f"({result.static_analysis_passed/result.total_tools*100:.1f}%)")
        
        print(f"   Passed: {result.individual_test_passed}/{result.total_tools} "
              f"({result.individual_test_passed/result.total_tools*100:.1f}%)")
        for tool in result.tools:
            status = "✅" if tool.individual_test_success else "❌"
            print(f"   {status} {tool.name}")
        
        if result.collective_test:
            status = "✅ PASS" if result.collective_test.success else "❌ FAIL"
            print(f"   Status: {status}")
            print(f"   Tools tested: {', '.join(result.collective_test.tools_tested)}")
            if result.collective_test.error_message:
                print(f"   Error: {result.collective_test.error_message[:100]}")
        
        print(f"\n⭐ High Quality Tools (static + individual + collective passed):")
        print(f"   Count: {result.high_quality_tools}/{result.total_tools} "
              f"({result.high_quality_tools/result.total_tools*100:.1f}%)")

        # Baseline
        if result.baseline_success is not None:
            baseline_status = "PASS" if result.baseline_success else "FAIL"
            print(f"\n📋 Baseline: {baseline_status}")
            if result.baseline_error:
                print(f"   Error: {result.baseline_error[:100]}")

        if result.project_classification:
            pc = result.project_classification
            print(f"\n🏷️  Classification: {pc.get('tool_organization', '?')} | "
                  f"{pc.get('complexity', '?')} | "
                  f"external_api={pc.get('has_external_api', '?')}")

        print(f"\n⏱️  Time: {result.total_time:.2f}s total")

        print("=" * 70)
    

    def _classify_project(self, workflow_dir: Path, actual_tool_count: Optional[int] = None) -> Dict[str, Any]:
        """

        Args:

        Returns:
            {
                'tool_organization': 'top_level' | 'nested_in_setup' | 'mixed',
                'complexity': 'simple' | 'medium' | 'complex',
                'has_external_api': bool,
            }
        """
        import ast as _ast

        classification = {
            'tool_organization': 'top_level',
            'tool_count': 0,
            'complexity': 'simple',
            'has_external_api': False,
        }

        skip_names = {
            'async_wrapper', 'sync_wrapper', 'wrapper', 'decorator',
            'default_serializer', 'info', 'error',
        }

        mcp_server_dir = workflow_dir / "mcp_server"
        has_nested_tools = False
        has_top_level_tools = False

        if mcp_server_dir.exists():
            for py_file in mcp_server_dir.rglob("*.py"):
                if '__pycache__' in str(py_file) or py_file.name == '__init__.py':
                    continue
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    file_tree = _ast.parse(content)

                    for node in file_tree.body:
                        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                            nested_children = [
                                child for child in _ast.walk(node)
                                if child is not node
                                and isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                                and child.name not in skip_names
                            ]
                            if nested_children:
                                has_nested_tools = True
                            for dec in node.decorator_list:
                                dec_str = _ast.dump(dec)
                                if 'tool' in dec_str.lower():
                                    has_top_level_tools = True
                                    break
                except Exception:
                    pass

        if has_nested_tools and has_top_level_tools:
            classification['tool_organization'] = 'mixed'
        elif has_nested_tools:
            classification['tool_organization'] = 'nested_in_setup'
        else:
            classification['tool_organization'] = 'top_level'

        tools = self._discover_tools(workflow_dir)
        classification['discovered_tools'] = len(tools)
        classification['tool_count'] = actual_tool_count if actual_tool_count is not None else len(tools)

        count = classification['tool_count']
        if count <= 5:
            classification['complexity'] = 'simple'
        elif count <= 10:
            classification['complexity'] = 'medium'
        else:
            classification['complexity'] = 'complex'

        workflow_json = workflow_dir / "workflow.json"
        if workflow_json.exists():
            try:
                with open(workflow_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                env_vars = data.get('configuration', {}).get('environment_variables', {})
                api_keywords = ['api_key', 'api_token', 'secret', 'token', 'oauth']
                for var_name in env_vars:
                    if any(kw in var_name.lower() for kw in api_keywords):
                        classification['has_external_api'] = True
                        break
            except Exception:
                pass

        return classification

    def _load_workflow_info(self, workflow_dir: Path) -> Dict[str, str]:
        workflow_json = workflow_dir / "workflow.json"
        if workflow_json.exists():
            try:
                with open(workflow_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                workflow_info = data.get('workflow', {})
                return {
                    'id': workflow_info.get('name', workflow_dir.name).lower().replace(' ', '_'),
                    'name': workflow_info.get('name', workflow_dir.name),
                }
            except Exception as e:
                logger.warning(f"Failed to load workflow info: {e}")
        return {'id': workflow_dir.name, 'name': workflow_dir.name}
    
    def _discover_tools(self, workflow_dir: Path) -> List[str]:
        tools = []

        def is_valid_tool(tool_name: str) -> bool:
            if not tool_name:
                return False
            if tool_name.startswith('builtin.'):
                return False
            if tool_name.startswith('n8n-nodes-base.') or tool_name.startswith('@n8n/'):
                return False
            return True

        workflow_json = workflow_dir / "workflow.json"
        if workflow_json.exists():
            try:
                with open(workflow_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for step in data.get('workflow_steps', []):
                    tool_name_or_list = step.get('mcp_tool')
                    if isinstance(tool_name_or_list, list):
                        for tool_name in tool_name_or_list:
                            if is_valid_tool(tool_name) and tool_name not in tools:
                                tools.append(tool_name)
                    elif is_valid_tool(tool_name_or_list) and tool_name_or_list not in tools:
                        tools.append(tool_name_or_list)
            except Exception as e:
                logger.warning(f"Failed to discover tools: {e}")
        
        # NOTE: workflow.json is the canonical source of MCP tools to evaluate.
        # The previous version also scanned `call_tool()` patterns in run_workflow.py,
        # but that adds tools not declared in workflow.json and causes off-by-N
        # inconsistencies between reported "Tools" count and Q1 tested count.
        # We now strictly use workflow.json. If a runner uses a tool not in
        # workflow.json, fix the project's workflow.json instead.
        call_tool_names = set()

        # Deduplicate by base name (strip trailing '_tool'), preferring call_tool names
        def base_name(s):
            s_lower = s.lower()
            if s_lower.endswith('_tool'):
                return s_lower[:-5]
            return s_lower

        seen_bases = {}  # base_name -> chosen tool name
        deduped = []
        for t in tools:
            bn = base_name(t)
            if bn not in seen_bases:
                seen_bases[bn] = t
                deduped.append(t)
            else:
                existing = seen_bases[bn]
                # Prefer the name that appears in call_tool() calls
                if t in call_tool_names and existing not in call_tool_names:
                    # Replace existing with this one
                    deduped = [t if x == existing else x for x in deduped]
                    seen_bases[bn] = t
                    logger.info(f"Dedup: replaced '{existing}' with '{t}' (used in call_tool)")
                else:
                    logger.info(f"Dedup: skipped '{t}' (keeping '{existing}')")

        return deduped
    
    def _find_original_tool(self, workflow_dir: Path, tool_name: str) -> Optional[Path]:
        """

        """
        import ast

        def search_in_file(file_path: Path) -> bool:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == tool_name:
                            return True

                        normalized_func = node.name.lower()
                        if normalized_func.endswith('_tool'):
                            normalized_func = normalized_func[:-5]
                        normalized_search = tool_name.lower()
                        if normalized_search.endswith('_tool'):
                            normalized_search = normalized_search[:-5]
                        if normalized_func == normalized_search:
                            return True
            except Exception as e:
                logger.warning(f"Failed to scan {file_path}: {e}")
            return False

        server_py = workflow_dir / "mcp_server" / "server.py"
        if server_py.exists() and search_in_file(server_py):
            logger.info(f"✓ Found '{tool_name}' in server.py")
            return server_py

        tools_dir = workflow_dir / "mcp_server" / "tools"
        if not tools_dir.exists():
            logger.warning(f"Tools directory not found: {tools_dir}")
            return None

        exact_match = tools_dir / f"{tool_name}.py"
        if exact_match.exists():
            logger.info(f"Found tool in dedicated file: {exact_match}")
            return exact_match

        logger.debug(f"Scanning for '{tool_name}' in all .py files...")

        for tool_file in tools_dir.glob("*.py"):
            if tool_file.name == "__init__.py":
                continue

            if search_in_file(tool_file):
                logger.info(f"✓ Found '{tool_name}' in {tool_file.name}")
                return tool_file

        for tool_file in tools_dir.rglob("*.py"):
            if "__pycache__" in str(tool_file) or tool_file.name == "__init__.py":
                continue

            if search_in_file(tool_file):
                logger.info(f"✓ Found '{tool_name}' in {tool_file.relative_to(tools_dir)}")
                return tool_file

        logger.warning(f"✗ Original tool '{tool_name}' not found in any file")
        return None

    def _save_generated_code(self, output_dir: Path, tool_name: str, code: str) -> Path:
        tools_dir = output_dir / "generated_tools"
        tools_dir.mkdir(exist_ok=True)
        tool_path = tools_dir / f"{tool_name}.py"
        with open(tool_path, 'w', encoding='utf-8') as f:
            f.write(code)
        return tool_path
    
    def _save_tool_evaluation(self, output_dir: Path, tool: RegeneratedTool):
        eval_dir = output_dir / "evaluations"
        eval_dir.mkdir(exist_ok=True)

        metrics_file = eval_dir / f"{tool.name}_metrics.json"
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(tool.to_dict(), f, indent=2, ensure_ascii=False)

        if tool.individual_test:
            if tool.individual_test.stdout:
                with open(eval_dir / f"{tool.name}_individual_stdout.txt", 'w') as f:
                    f.write(tool.individual_test.stdout)
            if tool.individual_test.stderr:
                with open(eval_dir / f"{tool.name}_individual_stderr.txt", 'w') as f:
                    f.write(tool.individual_test.stderr)
    
    def _save_workflow_result(self, output_dir: Path, result: RegenerationResult):
        result_file = output_dir / "workflow_result.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        if result.collective_test:
            if result.collective_test.stdout:
                with open(output_dir / "collective_test_stdout.txt", 'w') as f:
                    f.write(result.collective_test.stdout)
            if result.collective_test.stderr:
                with open(output_dir / "collective_test_stderr.txt", 'w') as f:
                    f.write(result.collective_test.stderr)
        
        logger.info(f"Saved workflow result: {result_file}")
