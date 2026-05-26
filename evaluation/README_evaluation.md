
# MCPFlow-Evaluation

This directory contains the streamlined evaluation code used for the MCP workflow benchmark.

## What is included

- `tasks/q1_tool_generation.py`: tool generation benchmark
- `tasks/q2_workflow_ordering.py`: workflow ordering benchmark
- `tasks/q3_incremental_evolution.py`: workflow extension benchmark
- `utils/`: shared helpers used by the three tasks
- `core/config.py`: configuration loading and validation

## Input format

Each project is expected to contain workflow artifacts such as:

- `workflow.json`
- `run_workflow.py`
- `pyproject.toml`
- `uv.lock`
- `mcp_server/`

## Usage

Create a local config from `config.example.yaml`, then run the desired task entry point with `uv run` or your local Python environment.

## Output

Evaluation results are written under the configured output directory and include per-project results and aggregated summaries.

## Notes

- This release keeps the evaluation code minimal and aligned with the public benchmark subset.
- Secret values and private URLs are not included in the released files.
