"""
"""
import json
import logging
import shlex
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class ProjectCommandManager:

    def __init__(self, verification_results_path: Optional[Path] = None):
        """

        Args:
        """
        self.commands_map: Dict[str, str] = {}
        self.projects_info: Dict[str, dict] = {}

        if verification_results_path and verification_results_path.exists():
            self._load_verification_results(verification_results_path)
        else:
            logger.warning(f"Verification results file not found: {verification_results_path}")

    def _load_verification_results(self, path: Path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                results = json.load(f)

            for project in results:
                project_name = project['name']
                self.commands_map[project_name] = project.get('command', 'python run_workflow.py')
                self.projects_info[project_name] = {
                    'status': project.get('status'),
                    'description': project.get('description'),
                    'arguments': project.get('arguments', []),
                    'requires_input': project.get('requires_input', False),
                    'mcp_tools': project.get('mcp_tools', []),
                }

            logger.info(f"Loaded commands for {len(self.commands_map)} projects")

        except Exception as e:
            logger.error(f"Failed to load verification results: {e}")

    def get_command(self, project_name: str) -> Optional[str]:
        """

        Args:

        Returns:
        """
        return self.commands_map.get(project_name)

    def get_command_list(self, project_name: str) -> Optional[List[str]]:
        """


        Args:

        Returns:
        """
        cmd = self.get_command(project_name)
        if not cmd:
            return None

        parts = shlex.split(cmd)

        env_vars = {}
        cmd_parts = []
        env_done = False
        for part in parts:
            if not env_done and '=' in part:
                key, _, value = part.partition('=')
                if key.isidentifier() and key == key.upper() and '/' not in value:
                    env_vars[key] = value
                    continue
            env_done = True
            cmd_parts.append(part)

        self._extra_env = env_vars
        if env_vars:
            logger.info(f"Extracted env vars from command: {env_vars}")

        return cmd_parts if cmd_parts else None

    def get_extra_env(self) -> Dict[str, str]:
        return getattr(self, '_extra_env', {})

    def get_project_info(self, project_name: str) -> Optional[dict]:
        """

        Args:

        Returns:
        """
        return self.projects_info.get(project_name)

    def is_runnable(self, project_name: str) -> bool:
        """

        Args:

        Returns:
        """
        info = self.get_project_info(project_name)
        if not info:
            return False

        return info['status'] == 'SUCCESS' and not info.get('requires_input', False)

    def get_runnable_projects(self) -> List[str]:
        """

        Returns:
        """
        return [
            name for name in self.projects_info.keys()
            if self.is_runnable(name)
        ]
