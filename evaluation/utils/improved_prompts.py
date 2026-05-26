"""
tasks/improved_prompts.py
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import ast
logger = logging.getLogger(__name__)


class ImprovedPromptBuilder:
    
    def __init__(self, workflow_dir: Path):
        self.workflow_dir = workflow_dir
        self.workflow_context = self._load_workflow_context()
        self.server_context = self._load_server_context()
        self.dependencies_context = self._load_dependencies_context()
    
    def build_tool_generation_prompt(
        self,
        tool_name: str,
        original_tool_path: Optional[Path] = None,
        include_examples: bool = True
    ) -> str:
        """
        
        Args:
        """
        tool_usage = self._extract_tool_usage(tool_name)
        
        original_signature = None
        if original_tool_path and original_tool_path.exists():
            original_signature = self._extract_tool_signature(
                original_tool_path, 
                tool_name  
            )
        
        prompt_parts = [
            self._build_header(),
            self._build_context_section(tool_name, tool_usage),
            self._build_requirements_section(original_signature),
            self._build_constraints_section(),
        ]
            
        prompt_parts.append(self._build_output_instructions())
        
        return "\n\n".join(prompt_parts)
    
    def _load_workflow_context(self) -> Dict[str, Any]:
        workflow_json = self.workflow_dir / "workflow.json"
        if not workflow_json.exists():
            return {}
        
        try:
            with open(workflow_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load workflow context: {e}")
            return {}
    
    def _load_server_context(self) -> Dict[str, Any]:
        server_py = self.workflow_dir / "mcp_server" / "server.py"
        if not server_py.exists():
            return {}
        
        try:
            with open(server_py, 'r', encoding='utf-8') as f:
                content = f.read()
            
            docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            docstring = docstring_match.group(1).strip() if docstring_match else ""
            
            return {
                'description': docstring,
                'has_fastmcp': '@mcp.tool()' in content or 'from mcp' in content.lower(),
            }
        except Exception as e:
            logger.warning(f"Failed to load server context: {e}")
            return {}
    
    def _load_dependencies_context(self) -> Dict[str, Any]:
        pyproject = self.workflow_dir / "pyproject.toml"
        if not pyproject.exists():
            return {}
        
        try:
            with open(pyproject, 'r', encoding='utf-8') as f:
                content = f.read()
            
            deps_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if deps_match:
                deps_text = deps_match.group(1)
                deps = [
                    dep.strip().strip('"').strip("'")
                    for dep in deps_text.split(',')
                    if dep.strip()
                ]
                return {'dependencies': deps}
        except Exception as e:
            logger.warning(f"Failed to load dependencies: {e}")
        
        return {}
    
    def _extract_tool_usage(self, tool_name: str) -> Dict[str, Any]:
        usage_info = {
            'step_description': None,
            'parameters_example': None,
            'context_snippets': [],
        }

        if self.workflow_context:
            for step in self.workflow_context.get('workflow_steps', []):
                if step.get('mcp_tool') == tool_name:
                    usage_info['step_description'] = step.get('description')
                    usage_info['parameters_example'] = step.get('parameters')
                    break
        
        run_workflow = self.workflow_dir / "run_workflow.py"
        if run_workflow.exists():
            try:
                with open(run_workflow, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                pattern = rf'call_tool\(\s*["\']({tool_name})["\']'
                for match in re.finditer(pattern, content):
                    start = max(0, match.start() - 200)
                    end = min(len(content), match.end() + 200)
                    snippet = content[start:end]
                    usage_info['context_snippets'].append(snippet)
            except Exception as e:
                logger.warning(f"Failed to extract tool usage: {e}")
        
        return usage_info
    
    def _build_signature_from_node(self, node, content: str) -> str:
        is_async = isinstance(node, ast.AsyncFunctionDef)
        func_prefix = "async def" if is_async else "def"

        params = []
        for arg in node.args.args:
            param_str = arg.arg
            if arg.annotation:
                if hasattr(ast, 'unparse'):
                    param_str += f": {ast.unparse(arg.annotation)}"
                else:
                    param_str += f": {ast.get_source_segment(content, arg.annotation) or 'Any'}"
            params.append(param_str)

        defaults = node.args.defaults
        if defaults:
            offset = len(node.args.args) - len(defaults)
            for i, default in enumerate(defaults):
                param_idx = offset + i
                if param_idx < len(params):
                    default_str = ast.unparse(default) if hasattr(ast, 'unparse') else '...'
                    params[param_idx] = f"{params[param_idx]} = {default_str}"

        params_str = ", ".join(params)

        return_type = ""
        if node.returns:
            if hasattr(ast, 'unparse'):
                return_type = f" -> {ast.unparse(node.returns)}"
            else:
                return_type = f" -> {ast.get_source_segment(content, node.returns) or 'Any'}"

        return f"{func_prefix} {node.name}({params_str}){return_type}"

    def _extract_tool_signature(self, tool_path: Path, tool_name: str) -> Optional[str]:
        """

        Args:

        Returns:
        """
        try:
            with open(tool_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == tool_name:
                        signature = self._build_signature_from_node(node, content)
                        logger.info(f"✓ Extracted signature: {signature}")
                        return signature

                    if self._fuzzy_match_name(node.name, tool_name):
                        logger.info(f"✓ Found '{tool_name}' via fuzzy match as '{node.name}'")
                        signature = self._build_signature_from_node(node, content)
                        logger.info(f"✓ Extracted signature: {signature}")
                        return signature

            logger.warning(f"✗ Function '{tool_name}' not found in {tool_path}")
            return None

        except Exception as e:
            logger.error(f"Failed to extract signature: {e}")
            return None

    def _fuzzy_match_name(self, name1: str, name2: str) -> bool:
        def normalize(s):
            s = s.lower()
            if s.endswith('_tool'):
                s = s[:-5]
            return s
        return normalize(name1) == normalize(name2)

    def _build_header(self) -> str:
        return """# MCP Tool Generation Task

You are an expert Python developer tasked with generating a **standalone tool function** for a FastMCP-based MCP server.

**Important Context:**
- The function you generate will be registered as an MCP tool by the server framework
- The server will add the `@mcp.tool()` decorator externally - you must NOT include it
- Your function must be completely **self-contained** and **stateless**
- The function will receive input ONLY through its parameters and return output through its return value"""
    
    def _build_context_section(
        self,
        tool_name: str,
        tool_usage: Dict[str, Any]
    ) -> str:
        sections = [
            "## Context",
            f"**Tool Name:** `{tool_name}`",
        ]
        
        if self.workflow_context:
            workflow_info = self.workflow_context.get('workflow', {})
            if workflow_info.get('description'):
                sections.append(f"**Workflow Purpose:** {workflow_info['description']}")
        
        if tool_usage.get('step_description'):
            sections.append(f"**Tool Purpose:** {tool_usage['step_description']}")
        
        if self.server_context.get('description'):
            sections.append(f"**Server Context:** {self.server_context['description']}")
        
        if tool_usage.get('parameters_example'):
            sections.append("**Usage Example:**")
            sections.append(f"```json\n{json.dumps(tool_usage['parameters_example'], indent=2)}\n```")
        
        if self.dependencies_context.get('dependencies'):
            deps = self.dependencies_context['dependencies']
            sections.append(f"**Available Dependencies:** {', '.join(deps[:5])}" + 
                          (f" (and {len(deps) - 5} more)" if len(deps) > 5 else ""))
        
        return "\n".join(sections)
    
    def _build_requirements_section(
        self,
        original_signature: Optional[str]
    ) -> str:
        requirements = [
            "## Requirements",
            "",
            "### CRITICAL Requirements (Must Follow):",
            "",
            "1. **Function Signature:**",
        ]
        
        if original_signature:
            requirements.extend([
                f"   - Must match this signature: `{original_signature}`",
                "   - Parameter names and types must be identical",
            ])
        else:
            requirements.extend([
                "   - Use descriptive parameter names",
                "   - All parameters must have type hints",
            ])
                
        return "\n".join(requirements)
    
    def _build_constraints_section(self) -> str:
        return """## Constraints

### CRITICAL - Function Must Be Self-Contained:
- Do NOT create or reference any MCP/FastMCP instance inside the function
  - No `mcp = MCP()` or `mcp = FastMCP()`
  - No `from fastmcp import MCP` inside the function
- Do NOT call any MCP framework methods inside the function body
  - No `mcp.log()`, `mcp.get_input()`, `mcp.context`, `mcp.tool()`, etc.
- The function must be a **pure function**: all input comes from parameters, all output via return value

### What NOT to do:
- Do NOT use `*args` or `**kwargs`
- Do NOT use `@mcp.tool()` decorator (the server adds it externally)
- Do NOT use `eval()`, `exec()`, or other dangerous operations
- Do NOT include test code or `if __name__ == "__main__"` blocks
- Do NOT add extra helper functions outside the main function

### Test Environment Constraints:
- External services (APIs, databases) may be unavailable in the test environment
- Wrap external API calls in try/except and provide sensible fallback/mock responses
- Do NOT assume environment variables contain valid API credentials
- Gracefully handle connection failures with reasonable default responses"""
    
    def _build_output_instructions(self) -> str:
        return """## Output Instructions

Generate ONLY the Python function code. 

**The output should start with `def` and end with the last line of the function.**"""

