"""
tasks/q1_tool_generation.py

"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List

from core.config import EvaluationConfig
from utils.llm_interface import LLMInterface
from utils.mcp_tool_regenerator import MCPToolRegenerator, RegenerationResult

logger = logging.getLogger(__name__)


@dataclass
class DatasetSummary:
    dataset_name: str

    total_workflows: int = 0
    total_tools: int = 0

    static_passed: int = 0

    individual_passed: int = 0


    high_quality_tools: int = 0

    baseline_passed: int = 0
    baseline_failed: int = 0

    # Effective metrics (only baseline-passing projects)
    effective_total_workflows: int = 0
    effective_total_tools: int = 0
    effective_individual_passed: int = 0
    effective_collective_passed: int = 0
    effective_high_quality_tools: int = 0

    total_time: float = 0.0

    workflow_results: List[Dict[str, Any]] = field(default_factory=list)

    def get_rates(self) -> Dict[str, float]:
        return {
            'static_pass_rate': self.static_passed / self.total_tools if self.total_tools > 0 else 0.0,
            'individual_pass_rate': self.individual_passed / self.total_tools if self.total_tools > 0 else 0.0,
            'collective_pass_rate': self.collective_passed / self.total_workflows if self.total_workflows > 0 else 0.0,
            'high_quality_rate': self.high_quality_tools / self.total_tools if self.total_tools > 0 else 0.0,
        }

    def get_effective_rates(self) -> Dict[str, float]:
        return {
            'effective_individual_pass_rate': self.effective_individual_passed / self.effective_total_tools if self.effective_total_tools > 0 else 0.0,
            'effective_collective_pass_rate': self.effective_collective_passed / self.effective_total_workflows if self.effective_total_workflows > 0 else 0.0,
            'effective_high_quality_rate': self.effective_high_quality_tools / self.effective_total_tools if self.effective_total_tools > 0 else 0.0,
        }

    def to_dict(self) -> Dict[str, Any]:
        rates = self.get_rates()
        effective_rates = self.get_effective_rates()
        return {
            'dataset_name': self.dataset_name,
            'statistics': {
                'workflows': {
                    'total': self.total_workflows,
                    'collective_passed': self.collective_passed,
                    'collective_pass_rate': rates['collective_pass_rate'],
                    'baseline_passed': self.baseline_passed,
                    'baseline_failed': self.baseline_failed,
                },
                'tools': {
                    'total': self.total_tools,
                    'static_passed': self.static_passed,
                    'static_pass_rate': rates['static_pass_rate'],
                    'individual_passed': self.individual_passed,
                    'individual_pass_rate': rates['individual_pass_rate'],
                    'high_quality': self.high_quality_tools,
                    'high_quality_rate': rates['high_quality_rate'],
                },
                'effective': {
                    'total_workflows': self.effective_total_workflows,
                    'total_tools': self.effective_total_tools,
                    'individual_passed': self.effective_individual_passed,
                    'individual_pass_rate': effective_rates['effective_individual_pass_rate'],
                    'collective_passed': self.effective_collective_passed,
                    'collective_pass_rate': effective_rates['effective_collective_pass_rate'],
                    'high_quality_tools': self.effective_high_quality_tools,
                    'high_quality_rate': effective_rates['effective_high_quality_rate'],
                },
                'time': self.total_time,
            },
            'workflow_results': self.workflow_results,
        }


@dataclass
class EvaluationSummary:

    total_datasets: int = 0
    total_workflows: int = 0
    total_tools: int = 0

    static_passed: int = 0
    individual_passed: int = 0
    collective_passed: int = 0
    high_quality_tools: int = 0

    baseline_passed: int = 0
    baseline_failed: int = 0

    # Effective metrics (only baseline-passing projects)
    effective_total_workflows: int = 0
    effective_total_tools: int = 0
    effective_individual_passed: int = 0
    effective_collective_passed: int = 0
    effective_high_quality_tools: int = 0

    total_time: float = 0.0

    layered_report: Optional[Dict[str, Any]] = None

    dataset_summaries: List[DatasetSummary] = field(default_factory=list)

    def get_rates(self) -> Dict[str, float]:
        return {
            'static_pass_rate': self.static_passed / self.total_tools if self.total_tools > 0 else 0.0,
            'individual_pass_rate': self.individual_passed / self.total_tools if self.total_tools > 0 else 0.0,
            'collective_pass_rate': self.collective_passed / self.total_workflows if self.total_workflows > 0 else 0.0,
            'high_quality_rate': self.high_quality_tools / self.total_tools if self.total_tools > 0 else 0.0,
        }

    def get_effective_rates(self) -> Dict[str, float]:
        return {
            'effective_individual_pass_rate': self.effective_individual_passed / self.effective_total_tools if self.effective_total_tools > 0 else 0.0,
            'effective_collective_pass_rate': self.effective_collective_passed / self.effective_total_workflows if self.effective_total_workflows > 0 else 0.0,
            'effective_high_quality_rate': self.effective_high_quality_tools / self.effective_total_tools if self.effective_total_tools > 0 else 0.0,
        }

    def to_dict(self) -> Dict[str, Any]:
        rates = self.get_rates()
        effective_rates = self.get_effective_rates()
        return {
            'overall_statistics': {
                'datasets': self.total_datasets,
                'workflows': {
                    'total': self.total_workflows,
                    'collective_passed': self.collective_passed,
                    'collective_pass_rate': rates['collective_pass_rate'],
                    'baseline_passed': self.baseline_passed,
                    'baseline_failed': self.baseline_failed,
                },
                'tools': {
                    'total': self.total_tools,
                    'static_passed': self.static_passed,
                    'static_pass_rate': rates['static_pass_rate'],
                    'individual_passed': self.individual_passed,
                    'individual_pass_rate': rates['individual_pass_rate'],
                    'high_quality': self.high_quality_tools,
                    'high_quality_rate': rates['high_quality_rate'],
                },
                'effective': {
                    'total_workflows': self.effective_total_workflows,
                    'total_tools': self.effective_total_tools,
                    'individual_passed': self.effective_individual_passed,
                    'individual_pass_rate': effective_rates['effective_individual_pass_rate'],
                    'collective_passed': self.effective_collective_passed,
                    'collective_pass_rate': effective_rates['effective_collective_pass_rate'],
                    'high_quality_tools': self.effective_high_quality_tools,
                    'high_quality_rate': effective_rates['effective_high_quality_rate'],
                },
                'time': self.total_time,
            },
            'layered_report': self.layered_report,
            'dataset_summaries': [ds.to_dict() for ds in self.dataset_summaries],
        }


class MCPToolEvaluator:
    
    def __init__(self, config: EvaluationConfig, llm_interface: LLMInterface):
        self.config = config
        self.llm = llm_interface
        self.regenerator = MCPToolRegenerator(config, llm_interface)
    
    async def evaluate_dataset(
        self,
        dataset_path: Path,
        output_dir: Optional[Path] = None,
        limit: Optional[int] = None
    ) -> EvaluationSummary:
        """
        
        """
        start_time = time.time()
        
        if output_dir is None:
            output_dir = Path("output")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_dir = output_dir / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Output directory: {output_dir}")
        
        self._backup_config(output_dir)
        
        dataset_dirs = self._find_dataset_directories(dataset_path)

        if not dataset_dirs:
            logger.error(f"No datasets found in: {dataset_path}")
            return EvaluationSummary()

        if limit is not None and limit > 0:
            original_count = len(dataset_dirs)
            dataset_dirs = dataset_dirs[:limit]
            logger.info(f"Found {original_count} dataset(s), limiting to first {len(dataset_dirs)}")
        else:
            logger.info(f"Found {len(dataset_dirs)} dataset(s) to evaluate")
        
        summary = EvaluationSummary()
        summary.total_datasets = len(dataset_dirs)
        
        for i, dataset_dir in enumerate(dataset_dirs, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"Evaluating dataset {i}/{len(dataset_dirs)}: {dataset_dir.name}")
            logger.info(f"{'='*80}")
            
            dataset_summary = await self._evaluate_single_dataset(
                dataset_dir=dataset_dir,
                output_dir=output_dir / dataset_dir.name
            )
            
            summary.dataset_summaries.append(dataset_summary)
            summary.total_workflows += dataset_summary.total_workflows
            summary.total_tools += dataset_summary.total_tools
            summary.static_passed += dataset_summary.static_passed
            summary.individual_passed += dataset_summary.individual_passed
            summary.collective_passed += dataset_summary.collective_passed
            summary.high_quality_tools += dataset_summary.high_quality_tools
            summary.baseline_passed += dataset_summary.baseline_passed
            summary.baseline_failed += dataset_summary.baseline_failed
            # Roll up effective metrics
            summary.effective_total_workflows += dataset_summary.effective_total_workflows
            summary.effective_total_tools += dataset_summary.effective_total_tools
            summary.effective_individual_passed += dataset_summary.effective_individual_passed
            summary.effective_collective_passed += dataset_summary.effective_collective_passed
            summary.effective_high_quality_tools += dataset_summary.effective_high_quality_tools

        summary.total_time = time.time() - start_time

        summary.layered_report = self._generate_layered_report(summary)

        self._save_total_summary(summary, output_dir)
        
        self._print_summary(summary)
        
        return summary
    
    async def _evaluate_single_dataset(
        self,
        dataset_dir: Path,
        output_dir: Path
    ) -> DatasetSummary:
        start_time = time.time()
        
        summary = DatasetSummary(dataset_name=dataset_dir.name)
        
        workflow_dirs = self._find_workflow_directories(dataset_dir)
        summary.total_workflows = len(workflow_dirs)
        
        if summary.total_workflows == 0:
            logger.warning(f"No workflows found in dataset: {dataset_dir.name}")
            return summary
        
        logger.info(f"Found {summary.total_workflows} workflow(s)")
        
        for workflow_dir in workflow_dirs:
            logger.info(f"\nProcessing workflow: {workflow_dir.name}")
            
            try:
                result: RegenerationResult = await self.regenerator.run_regeneration_evaluation(
                    workflow_dir=workflow_dir,
                    output_dir=output_dir / workflow_dir.name
                )
                
                summary.workflow_results.append({
                    'workflow_name': result.workflow_name,
                    'total_tools': result.total_tools,
                    'static_passed': result.static_analysis_passed,
                    'individual_passed': result.individual_test_passed,
                    'collective_success': result.collective_test_success,
                    'high_quality': result.high_quality_tools,
                    'baseline_success': result.baseline_success,
                    'project_classification': result.project_classification,
                })

                summary.total_tools += result.total_tools
                summary.static_passed += result.static_analysis_passed
                summary.individual_passed += result.individual_test_passed
                summary.high_quality_tools += result.high_quality_tools

                if result.collective_test_success:
                    summary.collective_passed += 1

                if result.baseline_success is True:
                    summary.baseline_passed += 1
                    # Accumulate effective metrics (baseline-passing projects only)
                    summary.effective_total_workflows += 1
                    summary.effective_total_tools += result.total_tools
                    summary.effective_individual_passed += result.individual_test_passed
                    summary.effective_high_quality_tools += result.high_quality_tools
                    if result.collective_test_success:
                        summary.effective_collective_passed += 1
                elif result.baseline_success is False:
                    summary.baseline_failed += 1
                
            except Exception as e:
                logger.error(f"Failed to evaluate workflow {workflow_dir.name}: {e}")
                summary.workflow_results.append({
                    'workflow_name': workflow_dir.name,
                    'error': str(e),
                })
        
        summary.total_time = time.time() - start_time

        self._save_dataset_summary(summary, output_dir)
        
        return summary
    
    def _find_dataset_directories(self, dataset_path: Path) -> List[Path]:
        if not dataset_path.exists():
            return []

        if (dataset_path / "workflow.json").exists():
            return [dataset_path]
        
        dataset_dirs = []
        for subdir in dataset_path.iterdir():
            if not subdir.is_dir():
                continue
            
            if (subdir / "workflow.json").exists():
                dataset_dirs.append(subdir)
            else:
                has_workflows = any(
                    (nested / "workflow.json").exists()
                    for nested in subdir.iterdir()
                    if nested.is_dir()
                )
                if has_workflows:
                    dataset_dirs.append(subdir)
        
        return sorted(dataset_dirs)
    
    def _find_workflow_directories(self, dataset_dir: Path) -> List[Path]:
        if (dataset_dir / "workflow.json").exists():
            return [dataset_dir]
        
        workflows = []
        for subdir in dataset_dir.iterdir():
            if subdir.is_dir() and (subdir / "workflow.json").exists():
                workflows.append(subdir)
        
        return sorted(workflows)
    
    def _backup_config(self, output_dir: Path):
        import datetime
        
        config_backup = {
            'backup_time': datetime.datetime.now().isoformat(),
            'config': self.config.to_dict(),
        }
        
        with open(output_dir / "config_backup.json", 'w') as f:
            json.dump(config_backup, f, indent=2)
    
    def _save_dataset_summary(self, summary: DatasetSummary, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_dir / "dataset_summary.json", 'w') as f:
            json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _save_total_summary(self, summary: EvaluationSummary, output_dir: Path):
        with open(output_dir / "total_summary.json", 'w') as f:
            json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _print_summary(self, summary: EvaluationSummary):
        rates = summary.get_rates()
        
        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)
        
        print(f" Datasets: {summary.total_datasets}")
        print(f" Workflows: {summary.total_workflows}")
        print(f" Tools: {summary.total_tools}")
        
        print(f"Results:")
        print(f"   Static Analysis Passed:  {summary.static_passed}/{summary.total_tools} "
              f"({rates['static_pass_rate']*100:.1f}%)")
        print(f"   Individual Test Passed:  {summary.individual_passed}/{summary.total_tools} "
              f"({rates['individual_pass_rate']*100:.1f}%)")
        print(f"   Collective Test Passed:  {summary.collective_passed}/{summary.total_workflows} workflows "
              f"({rates['collective_pass_rate']*100:.1f}%)")
        print(f"   High Quality Tools:      {summary.high_quality_tools}/{summary.total_tools} "
              f"({rates['high_quality_rate']*100:.1f}%)")

        print(f"\nBaseline: {summary.baseline_passed} passed, "
              f"{summary.baseline_failed} failed / {summary.total_workflows} workflows")

        # Effective metrics (baseline-passing projects only)
        effective_rates = summary.get_effective_rates()
        print(f"\nEffective Metrics (baseline-passing projects only):")
        print(f"   Workflows: {summary.effective_total_workflows}")
        print(f"   Tools: {summary.effective_total_tools}")
        print(f"   Individual Passed:   {summary.effective_individual_passed}/{summary.effective_total_tools} "
              f"({effective_rates['effective_individual_pass_rate']*100:.1f}%)")
        print(f"   Collective Passed:   {summary.effective_collective_passed}/{summary.effective_total_workflows} "
              f"({effective_rates['effective_collective_pass_rate']*100:.1f}%)")
        print(f"   High Quality Tools:  {summary.effective_high_quality_tools}/{summary.effective_total_tools} "
              f"({effective_rates['effective_high_quality_rate']*100:.1f}%)")

        print(f"\nTotal Time: {summary.total_time:.2f}s")

        if summary.layered_report:
            print("\n" + "-" * 80)
            print("LAYERED BREAKDOWN")
            print("-" * 80)

            by_org = summary.layered_report.get('by_tool_organization', {})
            if by_org:
                print("\nBy Tool Organization:")
                for org_type, stats in by_org.items():
                    print(f"  {org_type:20s}: {stats['workflow_count']} workflows, "
                          f"{stats['total_tools']:3d} tools, "
                          f"static={stats['static_pass_rate']*100:.1f}%, "
                          f"individual={stats['individual_pass_rate']*100:.1f}%, "
                          f"collective={stats['collective_pass_rate']*100:.1f}%")

            by_complexity = summary.layered_report.get('by_complexity', {})
            if by_complexity:
                print("\nBy Complexity:")
                for tier, stats in by_complexity.items():
                    print(f"  {tier:20s}: {stats['workflow_count']} workflows, "
                          f"{stats['total_tools']:3d} tools, "
                          f"individual={stats['individual_pass_rate']*100:.1f}%")

            by_baseline = summary.layered_report.get('by_baseline_status', {})
            if by_baseline:
                print("\nBy Baseline Status:")
                for status, stats in by_baseline.items():
                    print(f"  {status:20s}: {stats['workflow_count']} workflows, "
                          f"{stats['total_tools']:3d} tools, "
                          f"individual={stats['individual_pass_rate']*100:.1f}%")

        print("\n" + "=" * 80)

    def _generate_layered_report(self, summary: EvaluationSummary) -> Dict[str, Any]:
        """
        """
        report = {
            'by_tool_organization': {},
            'by_complexity': {},
            'by_baseline_status': {},
            'effective_overall': {},
        }

        all_results = []
        for ds in summary.dataset_summaries:
            for wr in ds.workflow_results:
                all_results.append(wr)

        def _compute_group_stats(group: List[Dict]) -> Dict[str, Any]:
            total_tools = sum(r.get('total_tools', 0) for r in group)
            static_passed = sum(r.get('static_passed', 0) for r in group)
            indiv_passed = sum(r.get('individual_passed', 0) for r in group)
            collective_passed = sum(1 for r in group if r.get('collective_success'))
            hq = sum(r.get('high_quality', 0) for r in group)
            return {
                'workflow_count': len(group),
                'total_tools': total_tools,
                'static_pass_rate': static_passed / total_tools if total_tools > 0 else 0.0,
                'individual_pass_rate': indiv_passed / total_tools if total_tools > 0 else 0.0,
                'collective_pass_rate': collective_passed / len(group) if group else 0.0,
                'high_quality_rate': hq / total_tools if total_tools > 0 else 0.0,
            }

        for org_type in ['top_level', 'nested_in_setup', 'mixed']:
            group = [r for r in all_results
                     if r.get('project_classification', {}).get('tool_organization') == org_type]
            if group:
                report['by_tool_organization'][org_type] = _compute_group_stats(group)

        for tier in ['simple', 'medium', 'complex']:
            group = [r for r in all_results
                     if r.get('project_classification', {}).get('complexity') == tier]
            if group:
                report['by_complexity'][tier] = _compute_group_stats(group)

        for label, value in [('baseline_pass', True), ('baseline_fail', False)]:
            group = [r for r in all_results
                     if r.get('baseline_success') is value]
            if group:
                report['by_baseline_status'][label] = _compute_group_stats(group)

        # Effective overall: stats only for baseline-passing projects
        effective_group = [r for r in all_results if r.get('baseline_success') is True]
        if effective_group:
            report['effective_overall'] = _compute_group_stats(effective_group)

        return report


async def main():
    import argparse
    from utils.logger import setup_logger
    
    parser = argparse.ArgumentParser(description="MCP Tool Evaluator")
    parser.add_argument("--dataset", type=str, required=True, help="Dataset path")
    parser.add_argument("--output", type=str, default="output", help="Output directory")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config file")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of projects to evaluate")
    
    args = parser.parse_args()
    
    setup_logger()
    
    config = EvaluationConfig(args.config)
    llm = LLMInterface(config.llm_config)
    
    evaluator = MCPToolEvaluator(config, llm)

    await evaluator.evaluate_dataset(
        dataset_path=Path(args.dataset),
        output_dir=Path(args.output),
        limit=args.limit
    )

if __name__ == "__main__":
    asyncio.run(main())
