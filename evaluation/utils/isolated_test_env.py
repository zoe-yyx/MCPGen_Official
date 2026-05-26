"""
tasks/isolated_test_env.py (FINAL FIX: Better Success Detection)

"""
import ast
import os
import shutil
import tempfile
import subprocess
import sys
import time
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import ProjectCommandManager
try:
    from utils.project_commands import ProjectCommandManager
except ImportError:
    logger.warning("Could not import ProjectCommandManager")
    ProjectCommandManager = None


class ToolReplacer:

    @staticmethod
    def find_tool_location(tools_dir: Path, tool_name: str) -> Optional[Tuple[Path, str]]:

        def search_in_file(py_file: Path) -> Optional[Tuple[Path, str]]:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == tool_name:
                            return (py_file, node.name)

                        if ToolReplacer._fuzzy_match(node.name, tool_name):
                            return (py_file, node.name)

            except Exception as e:
                logger.warning(f"Failed to parse {py_file}: {e}")
            return None

        mcp_server_dir = tools_dir.parent
        server_py = mcp_server_dir / "server.py"
        if server_py.exists():
            result = search_in_file(server_py)
            if result:
                return result

        if not tools_dir.exists():
            logger.error(f"Tools directory not found: {tools_dir}")
            return None

        py_files = list(tools_dir.rglob("*.py"))

        for py_file in py_files:
            if py_file.name == "__init__.py" or '__pycache__' in str(py_file):
                continue

            result = search_in_file(py_file)
            if result:
                return result

        return None
    
    @staticmethod
    def _fuzzy_match(name1: str, name2: str) -> bool:
        def normalize(s):
            s = s.lower()
            if s.endswith('_tool'):
                s = s[:-5]
            return s
        return normalize(name1) == normalize(name2)
    
    @staticmethod
    def replace_function_in_file(
        file_path: Path,
        function_name: str,
        new_code: str,
        debug_dir: Optional[Path] = None
    ) -> Tuple[bool, str]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            if debug_dir:
                debug_dir.mkdir(parents=True, exist_ok=True)
                with open(debug_dir / f"{file_path.name}.original", 'w') as f:
                    f.write(original_content)

            tree = ast.parse(original_content)

            target_node = None
            is_async = False

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                    target_node = node
                    is_async = isinstance(node, ast.AsyncFunctionDef)
                    break

            if not target_node:
                return False, f"Function '{function_name}' not found"

            start_line = target_node.lineno - 1
            end_line = target_node.end_lineno

            if target_node.decorator_list:
                start_line = target_node.decorator_list[0].lineno - 1

            original_lines = original_content.split('\n')

            decorators = []
            for decorator in target_node.decorator_list:
                dec_start = decorator.lineno - 1
                dec_end = decorator.end_lineno
                decorators.append('\n'.join(original_lines[dec_start:dec_end]))

            if is_async and not new_code.strip().startswith('async def'):
                new_code = new_code.replace('def ', 'async def ', 1)

            original_has_self = (
                target_node.args.args and
                len(target_node.args.args) > 0 and
                target_node.args.args[0].arg == 'self'
            )

            new_has_self = False
            try:
                new_tree = ast.parse(new_code)
                for node in ast.walk(new_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.args.args and len(node.args.args) > 0 and node.args.args[0].arg == 'self':
                            new_has_self = True
                            break
            except (SyntaxError, ValueError, AttributeError):
                pass

            if not original_has_self and new_has_self:
                nc_lines = new_code.split('\n')
                for i, line in enumerate(nc_lines):
                    if re.match(r'^\s*(async\s+)?def\s+', line):
                        nc_lines[i] = re.sub(r'\(\s*self\s*,\s*', '(', line, count=1)
                        nc_lines[i] = re.sub(r'\(\s*self\s*\)', '()', nc_lines[i], count=1)
                        break
                new_code = '\n'.join(nc_lines)

            original_func_line = original_lines[target_node.lineno - 1]
            original_indent = len(original_func_line) - len(original_func_line.lstrip())

            new_code_lines = new_code.split('\n')
            new_code_indent = 0
            for line in new_code_lines:
                stripped = line.lstrip()
                if stripped.startswith('def ') or stripped.startswith('async def '):
                    new_code_indent = len(line) - len(stripped)
                    break

            indent_delta = original_indent - new_code_indent

            if indent_delta != 0:
                adjusted_lines = []
                for line in new_code_lines:
                    if indent_delta > 0:
                        adjusted_lines.append(' ' * indent_delta + line)
                    else:
                        remove = min(abs(indent_delta), len(line) - len(line.lstrip()))
                        adjusted_lines.append(line[remove:])
                new_code = '\n'.join(adjusted_lines)

            before = '\n'.join(original_lines[:start_line])
            after = '\n'.join(original_lines[end_line:])

            new_content_parts = []
            if before.strip():
                new_content_parts.append(before)
            if new_content_parts:
                new_content_parts.append('')

            for dec in decorators:
                new_content_parts.append(dec)
            new_content_parts.append(new_code)

            if after.strip():
                new_content_parts.append('')
                new_content_parts.append(after)

            new_content = '\n'.join(new_content_parts)

            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return False, f"Syntax error: {e.msg}"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            if debug_dir:
                with open(debug_dir / f"{file_path.name}.replaced", 'w') as f:
                    f.write(new_content)

            return True, ""

        except Exception as e:
            return False, str(e)


class IsolatedTestEnvironment:
    
    def __init__(
        self,
        workflow_dir: Path,
        keep_on_error: bool = False,
        debug_dir: Optional[Path] = None,
        command_manager: Optional['ProjectCommandManager'] = None
    ):
        self.original_workflow_dir = workflow_dir.resolve()
        self.keep_on_error = keep_on_error
        self.debug_dir = debug_dir
        self.command_manager = command_manager

        self.temp_root: Optional[Path] = None
        self.test_workflow_dir: Optional[Path] = None

        self._test_success = True
        self._tool_locations: Dict[str, Tuple[Path, str]] = {}
        self._install_logs: List[Dict[str, Any]] = []
    
    def __enter__(self):
        self.temp_root = Path(tempfile.mkdtemp(prefix="mcp_isolated_test_"))
        
        self.test_workflow_dir = self.temp_root / self.original_workflow_dir.name
        
        try:
            shutil.copytree(
                self.original_workflow_dir,
                self.test_workflow_dir,
                symlinks=False,
                ignore_dangling_symlinks=True
            )
        except Exception as e:
            logger.error(f"Failed to copy workflow: {e}")
            self._cleanup()
            raise
        
        self._scan_tool_locations()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._test_success = False
        
        if not self._test_success and self.keep_on_error:
            logger.info(f"Keeping environment: {self.temp_root}")
        else:
            self._cleanup()
    
    def _cleanup(self):
        if self.temp_root and self.temp_root.exists():
            try:
                shutil.rmtree(self.temp_root)
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
    
    def _scan_tool_locations(self):
        self._tool_locations.clear()

        def scan_file(py_file: Path):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith('_'):
                            self._tool_locations[node.name] = (py_file, node.name)

            except Exception as e:
                logger.warning(f"Failed to scan {py_file}: {e}")

        server_py = self.test_workflow_dir / "mcp_server" / "server.py"
        if server_py.exists():
            scan_file(server_py)

        tools_dir = self.get_tools_dir()

        if not tools_dir.exists():
            if not server_py.exists():
                logger.error(f"Tools directory not found: {tools_dir}")
            return

        py_files = list(tools_dir.rglob("*.py"))
        py_files = [f for f in py_files if '__pycache__' not in str(f)]

        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue

            scan_file(py_file)
    
    def get_test_workflow_dir(self) -> Path:
        if not self.test_workflow_dir:
            raise RuntimeError("Environment not initialized")
        return self.test_workflow_dir
    
    def get_tools_dir(self) -> Path:
        base = self.get_test_workflow_dir()
        
        for location in [
            base / "mcp_server" / "tools",
            base / "tools",
            base / "mcp_server" / "src" / "tools",
            base / "src" / "tools",
        ]:
            if location.exists():
                return location
        
        return base / "mcp_server" / "tools"
    
    def get_tool_location(self, tool_name: str) -> Optional[Tuple[Path, str]]:
        if tool_name in self._tool_locations:
            return self._tool_locations[tool_name]
        
        normalized_search = tool_name.lower()
        if normalized_search.endswith('_tool'):
            normalized_search = normalized_search[:-5]
        for cached_name, location in self._tool_locations.items():
            normalized_cached = cached_name.lower()
            if normalized_cached.endswith('_tool'):
                normalized_cached = normalized_cached[:-5]
            if normalized_cached == normalized_search:
                return location
        
        return ToolReplacer.find_tool_location(self.get_tools_dir(), tool_name)
    
    def get_available_tools(self) -> List[str]:
        return list(self._tool_locations.keys())
    
    def install_regenerated_tool(self, tool_name: str, code: str) -> Tuple[bool, str]:
        install_log = {
            'tool_name': tool_name,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'error': None,
        }
        
        location = self.get_tool_location(tool_name)
        
        if not location:
            available = self.get_available_tools()
            error_msg = f"Tool '{tool_name}' not found. Available: {available[:10]}"
            install_log['error'] = error_msg
            self._install_logs.append(install_log)
            return False, error_msg
        
        file_path, actual_function_name = location
        
        if tool_name != actual_function_name:
            code = self._adjust_function_name(code, tool_name, actual_function_name)
        
        success, error_msg = ToolReplacer.replace_function_in_file(
            file_path=file_path,
            function_name=actual_function_name,
            new_code=code,
            debug_dir=self.debug_dir
        )
        
        install_log['success'] = success
        install_log['error'] = error_msg if not success else None
        self._install_logs.append(install_log)
        
        return success, error_msg
    
    def _adjust_function_name(self, code: str, expected: str, actual: str) -> str:
        code = re.sub(rf'def\s+{re.escape(expected)}\s*\(', f'def {actual}(', code, count=1)
        code = re.sub(rf'async\s+def\s+{re.escape(expected)}\s*\(', f'async def {actual}(', code, count=1)
        return code
    
    def run_workflow_test(self, timeout: float = 60.0) -> Dict[str, Any]:
        start_time = time.time()
        workflow_dir = self.get_test_workflow_dir()
        
        result = {
            'success': False,
            'returncode': -1,
            'stdout': None,
            'stderr': None,
            'execution_time': 0,
            'error': None,
            'command': None,
            'working_dir': str(workflow_dir),
            'install_logs': self._install_logs,
            'log_files': {},
        }
        
        run_workflow = workflow_dir / "run_workflow.py"
        if not run_workflow.exists():
            result['error'] = "run_workflow.py not found"
            return result

        cmd = None
        extra_env = {}
        if self.command_manager:
            project_name = workflow_dir.name
            cmd_list = self.command_manager.get_command_list(project_name)
            if cmd_list:
                cmd = cmd_list
                extra_env = self.command_manager.get_extra_env()
                logger.info(f"Using command from verification results: {' '.join(cmd)}")

        if not cmd:
            if (workflow_dir / "pyproject.toml").exists() and (workflow_dir / "uv.lock").exists():
                cmd = ["uv", "run", "--active", "python", "run_workflow.py"]
            else:
                cmd = [sys.executable, "run_workflow.py"]
            logger.info(f"Using default command: {' '.join(cmd)}")

        result['command'] = ' '.join(cmd)

        # Setup environment with mock/test values
        test_env = os.environ.copy()
        test_env['MCP_MOCK_ENABLED'] = 'true'
        test_env['MOCK_MODE'] = 'true'

        if extra_env:
            test_env.update(extra_env)

        # Auto-mock environment variables from workflow.json
        workflow_json_path = self.original_workflow_dir / "workflow.json"
        if workflow_json_path.exists():
            try:
                with open(workflow_json_path, 'r', encoding='utf-8') as f:
                    wf_data = json.load(f)
                env_vars = wf_data.get('configuration', {}).get('environment_variables', {})
                for var_name, var_config in env_vars.items():
                    if var_name not in test_env or not test_env[var_name]:
                        # Use example value if available, otherwise generate mock
                        if isinstance(var_config, dict) and var_config.get('example'):
                            test_env[var_name] = str(var_config['example'])
                        else:
                            test_env[var_name] = self._generate_smart_mock_value(var_name)
            except Exception as e:
                logger.warning(f"Failed to read env vars from workflow.json: {e}")

        # Legacy hardcoded fallbacks for common keys
        test_env.setdefault('OPENAI_API_KEY', 'REDACTED_API_KEY')
        test_env.setdefault('OPENAI_BASE_URL', '')
        test_env.setdefault('GOOGLE_API_KEY', 'mock-google-api-key')
        test_env.setdefault('ANTHROPIC_API_KEY', 'mock-anthropic-api-key')

        try:
            proc_result = subprocess.run(
                cmd,
                cwd=workflow_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=test_env
            )
            
            result['returncode'] = proc_result.returncode
            result['stdout'] = proc_result.stdout
            result['stderr'] = proc_result.stderr
            result['execution_time'] = time.time() - start_time
            
            has_error_in_stderr = self._detect_errors_in_stderr(proc_result.stderr)
            
            result['success'] = (
                proc_result.returncode == 0 and 
                not has_error_in_stderr
            )
            
            if not result['success']:
                if has_error_in_stderr:
                    result['error'] = "Workflow failed: errors detected in stderr"
                else:
                    result['error'] = f"Exit code {proc_result.returncode}"
            
        except subprocess.TimeoutExpired as e:
            result['error'] = f"Timeout after {timeout}s"
            result['execution_time'] = timeout
            
        except Exception as e:
            result['error'] = str(e)
            result['execution_time'] = time.time() - start_time
        
        result['log_files'] = self._collect_log_files(workflow_dir)
        
        return result
    
    @staticmethod
    def _generate_smart_mock_value(var_name: str) -> str:
        name_lower = var_name.lower()

        numeric_keywords = [
            'port', 'timeout', 'interval', 'attempts', 'retries', 'retry',
            'max', 'min', 'limit', 'count', 'size', 'width', 'height',
            'rate', 'duration', 'delay', 'workers', 'threads', 'batch',
            'threshold', 'tokens', 'length', 'depth', 'concurrent', 'page',
            'polling', 'ttl', 'expires', 'age',
        ]
        if any(kw in name_lower for kw in numeric_keywords):
            if 'port' in name_lower:
                return '8080'
            if 'timeout' in name_lower or 'ttl' in name_lower or 'expires' in name_lower:
                return '30'
            if 'interval' in name_lower or 'delay' in name_lower or 'polling' in name_lower:
                return '5'
            if 'width' in name_lower or 'height' in name_lower:
                return '512'
            if 'tokens' in name_lower:
                return '2000'
            return '10'

        url_keywords = ['url', 'endpoint', 'host', 'base_url', 'webhook', 'callback', 'uri']
        if any(kw in name_lower for kw in url_keywords):
            return 'ENDPOINT_PLACEHOLDER'

        if 'email' in name_lower or 'mail_address' in name_lower:
            return 'EMAIL_PLACEHOLDER'

        bool_keywords = ['enabled', 'disabled', 'debug', 'verbose', 'flag', 'active', 'use_']
        if any(kw in name_lower for kw in bool_keywords):
            return 'true'

        path_keywords = ['path', 'dir', 'directory', 'folder', 'file']
        if any(kw in name_lower for kw in path_keywords):
            return '/tmp/mock'

        return f"mock-{var_name.lower()}-for-testing"

    def _detect_errors_in_stderr(self, stderr: Optional[str]) -> bool:
        """


        Returns:
        """
        if not stderr:
            return False

        if '\u274c' in stderr:  # ❌ emoji
            return True
        if 'error calling tool' in stderr.lower():
            return True

        # 1b. Application-level error patterns (Python logging ERROR level)
        for line in stderr.split('\n'):
            stripped = line.strip()
            if stripped.startswith('ERROR - ') or stripped.startswith('ERROR:'):
                lower_msg = stripped.lower()
                if any(kw in lower_msg for kw in ['failed', 'error:', 'exception', 'traceback']):
                    return True

        if 'Traceback (most recent call last)' in stderr:
            return True

        exception_types = [
            'TypeError', 'AttributeError', 'ValueError', 'KeyError',
            'ImportError', 'ModuleNotFoundError', 'NameError',
            'SyntaxError', 'RuntimeError', 'ConnectionError',
            'FileNotFoundError', 'PermissionError', 'OSError',
            'IOError', 'IndexError', 'ZeroDivisionError',
            'RecursionError', 'MemoryError', 'NotImplementedError',
        ]
        for line in stderr.split('\n'):
            stripped = line.lstrip()
            for exc_type in exception_types:
                if stripped.startswith(exc_type + ':') or stripped.startswith(exc_type + '('):
                    return True

        return False
    
    def _collect_log_files(self, workflow_dir: Path) -> Dict[str, str]:
        log_contents = {}
        
        logs_dir = workflow_dir / "logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("**/*"):
                if log_file.is_file():
                    try:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        rel_path = log_file.relative_to(workflow_dir)
                        log_contents[str(rel_path)] = content
                    except Exception as e:
                        logger.warning(f"Failed to read {log_file}: {e}")
        
        for log_file in workflow_dir.glob("*.log"):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                log_contents[log_file.name] = content
            except Exception as e:
                logger.warning(f"Failed to read {log_file}: {e}")
        
        return log_contents


class TestRunner:

    def __init__(
        self,
        workflow_dir: Path,
        timeout: float = 60.0,
        output_dir: Optional[Path] = None,
        command_manager: Optional['ProjectCommandManager'] = None
    ):
        self.workflow_dir = workflow_dir.resolve()
        self.timeout = timeout
        self.output_dir = output_dir
        self.command_manager = command_manager
        self._test_counter = 0
    
    def _get_debug_dir(self, test_name: str) -> Optional[Path]:
        if not self.output_dir:
            return None
        
        self._test_counter += 1
        debug_dir = self.output_dir / "debug" / f"{self._test_counter:03d}_{test_name}"
        debug_dir.mkdir(parents=True, exist_ok=True)
        return debug_dir
    
    def _save_test_result(self, debug_dir: Path, result: Dict[str, Any], test_type: str):
        if not debug_dir:
            return
        
        with open(debug_dir / "result.json", 'w') as f:
            serializable = {k: v for k, v in result.items() 
                          if k not in ['stdout', 'stderr', 'log_files']}
            json.dump(serializable, f, indent=2, default=str)
        
        if result.get('stdout'):
            with open(debug_dir / "stdout.log", 'w') as f:
                f.write(result['stdout'])
        
        if result.get('stderr'):
            with open(debug_dir / "stderr.log", 'w') as f:
                f.write(result['stderr'])
        
        if result.get('install_logs'):
            with open(debug_dir / "install_logs.json", 'w') as f:
                json.dump(result['install_logs'], f, indent=2, default=str)
        
        if result.get('log_files'):
            workflow_logs_dir = debug_dir / "workflow_logs"
            workflow_logs_dir.mkdir(exist_ok=True)
            
            for log_path, log_content in result['log_files'].items():
                safe_path = log_path.replace('/', '_').replace('\\', '_')
                with open(workflow_logs_dir / safe_path, 'w') as f:
                    f.write(log_content)
        
        with open(debug_dir / "summary.txt", 'w') as f:
            f.write(f"Test Type: {test_type}\n")
            f.write(f"Success: {result.get('success', False)}\n")
            f.write(f"Return Code: {result.get('returncode', -1)}\n")
            f.write(f"Execution Time: {result.get('execution_time', 0):.2f}s\n")
            f.write(f"Error: {result.get('error', 'None')}\n")
    
    def run_individual_test(self, tool_name: str, tool_code: str) -> Dict[str, Any]:
        logger.info(f"[Individual Test] {tool_name}")
        debug_dir = self._get_debug_dir(f"individual_{tool_name}")
        
        if debug_dir:
            with open(debug_dir / "generated_code.py", 'w') as f:
                f.write(tool_code)
        
        result = {
            'success': False,
            'error': None,
            'tool_name': tool_name,
        }
        
        if not tool_code:
            result['error'] = 'No code generated'
            if debug_dir:
                self._save_test_result(debug_dir, result, f"individual_{tool_name}")
            return result
        
        with IsolatedTestEnvironment(self.workflow_dir, debug_dir=debug_dir, command_manager=self.command_manager) as env:
            success, error_msg = env.install_regenerated_tool(tool_name, tool_code)

            if not success:
                result['error'] = f"Failed to install: {error_msg}"
                result['install_logs'] = env._install_logs
                if debug_dir:
                    self._save_test_result(debug_dir, result, f"individual_{tool_name}")
                return result

            exec_result = env.run_workflow_test(timeout=self.timeout)
            result.update(exec_result)

        if debug_dir:
            self._save_test_result(debug_dir, result, f"individual_{tool_name}")

        status = "✅ PASS" if result['success'] else "❌ FAIL"
        logger.info(f"[Individual Test] {tool_name}: {status}")

        return result

    def run_collective_test(self, tools: Dict[str, str]) -> Dict[str, Any]:
        logger.info(f"[Collective Test] Testing {len(tools)} tools")
        debug_dir = self._get_debug_dir("collective_all")

        result = {
            'success': False,
            'tools_requested': list(tools.keys()),
            'tools_installed': [],
            'tools_failed': [],
        }

        with IsolatedTestEnvironment(self.workflow_dir, debug_dir=debug_dir, command_manager=self.command_manager) as env:
            for tool_name, tool_code in tools.items():
                if not tool_code:
                    result['tools_failed'].append({
                        'name': tool_name,
                        'error': 'No code generated'
                    })
                    continue
                
                success, error_msg = env.install_regenerated_tool(tool_name, tool_code)
                if success:
                    result['tools_installed'].append(tool_name)
                else:
                    result['tools_failed'].append({
                        'name': tool_name,
                        'error': error_msg
                    })
            
            if result['tools_installed']:
                exec_result = env.run_workflow_test(timeout=self.timeout)
                result.update(exec_result)
        
        if debug_dir:
            self._save_test_result(debug_dir, result, "collective")
        
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        logger.info(f"[Collective Test] {status}")
        
        return result
    
    def run_all_tests(self, tools: Dict[str, str], project_time_budget: float = 0) -> Dict[str, Any]:
        """
        Run all individual and collective tests.

        Args:
            tools: dict of tool_name -> generated code
            project_time_budget: max seconds for all tests combined (0 = unlimited)
        """
        budget_start = time.time()
        results = {
            'individual_results': {},
            'collective_result': None,
            'summary': {
                'total_tools': len(tools),
                'individual_passed': 0,
                'collective_passed': False,
                'budget_exceeded': False,
            }
        }

        logger.info("=" * 60)
        logger.info("Phase: Individual Tool Tests")
        logger.info("=" * 60)

        for tool_name, tool_code in tools.items():
            # Check time budget before each individual test
            if project_time_budget > 0:
                elapsed = time.time() - budget_start
                if elapsed >= project_time_budget:
                    logger.warning(f"Project time budget ({project_time_budget}s) exceeded after {elapsed:.1f}s, "
                                   f"skipping remaining individual tests")
                    results['summary']['budget_exceeded'] = True
                    results['individual_results'][tool_name] = {
                        'success': False,
                        'error': f'Skipped: project time budget exceeded ({elapsed:.1f}s / {project_time_budget}s)',
                        'tool_name': tool_name,
                    }
                    continue

            result = self.run_individual_test(tool_name, tool_code)
            results['individual_results'][tool_name] = result
            if result.get('success'):
                results['summary']['individual_passed'] += 1

        logger.info("=" * 60)
        logger.info("Phase: Collective Workflow Test")
        logger.info("=" * 60)

        # Check time budget before collective test
        if project_time_budget > 0:
            elapsed = time.time() - budget_start
            if elapsed >= project_time_budget:
                logger.warning(f"Project time budget exceeded, skipping collective test")
                results['summary']['budget_exceeded'] = True
                return results

        valid_tools = {k: v for k, v in tools.items() if v}
        if valid_tools:
            results['collective_result'] = self.run_collective_test(valid_tools)
            results['summary']['collective_passed'] = results['collective_result'].get('success', False)

        return results
