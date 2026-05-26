# Employee Leave Alert System

An MCP-based automation that manages employee leave notifications. Converted from an n8n workflow.

## Overview

This project checks employee leave records daily and:
- **Activates** leave: sends Slack notification + OOO reminder email + marks record as Active
- **Resets** leave: sends Slack return notification + Welcome Back email + marks record as Inactive

All external services (Google Sheets, Slack, Gmail) are **mocked** using local JSON files.

## Project Structure

```
mcp_project68/
├── data/leave_records.json          # Mock employee leave data
├── mcp_server/
│   ├── server.py                    # MCP server with 8 registered tools
│   └── tools/
│       ├── leave_tools.py           # Google Sheets mock (fetch, validate, update)
│       ├── notification_tools.py    # Slack mock (HR channel notifications)
│       ├── email_tools.py           # Gmail mock (OOO + welcome back emails)
│       └── utils/log_decorator.py  # Logging utilities
├── tests/test_tools.py              # Unit tests
├── results/outputs/                 # Slack notifications + emails saved here
├── results/metrics/                 # Workflow run metrics
├── run_workflow.py                  # Main workflow executor
└── workflow.json                    # Step definitions
```

## Setup

1. Install dependencies using `uv`:
```bash
cd mcp_project68
uv sync
```

2. (Optional) The `.env.template` shows available config options. No API keys needed for mock mode.

## Running the MCP Server

```bash
cd mcp_project68
uv run python mcp_server/server.py
```

## Running the Workflow

```bash
cd mcp_project68
uv run python run_workflow.py
```

The workflow will:
1. Read `data/leave_records.json`
2. Compute which employees need activation or reset (based on today's date)
3. Send mock Slack notifications - saved to `results/outputs/slack_notifications.json`
4. Send mock emails - saved to `results/outputs/emails.json`
5. Update statuses in `data/leave_records.json`
6. Save run metrics to `results/metrics/workflow_metrics.json`

## Running Tests

```bash
cd mcp_project68
uv run python -m pytest tests/ -v
```

## Mock Data

Edit `data/leave_records.json` to add employees. Expected fields:
- `Employee Email` (required)
- `Name`
- `Start Date` (YYYY-MM-DD, required)
- `End Date` (YYYY-MM-DD, required)
- `Status` (`Active` / `Inactive`)
- `Last Updated`

## Notes

- Re-running the workflow on the same day is idempotent: already-Active records are skipped for activation; already-Inactive ended records are skipped for reset.
- Logs are written to `logs/workflow.log` and `logs/server.log`.
