# Turn Google Tasks into n8n Plans with Slack Approval & Archiving

MCP project converted from n8n workflow. Fetches unprocessed Google Tasks ideas daily, uses GPT to design complete n8n workflow plans, sends them to Slack for human review (Approve/Regenerate), archives approved plans to Google Sheets, and marks tasks as processed.

## Workflow Paths

| Step | Name | Description |
|------|------|-------------|
| 1 | Schedule Trigger | Daily 9am trigger (inline) |
| 2 | Get New Ideas | Fetch up to 5 tasks from mock Google Tasks |
| 3 | Filter Processed | Skip tasks with "✅ Processed" in notes |
| 4 | Iterate Ideas | Loop through each unprocessed idea |
| 5 | AI Solution Architect | GPT generates n8n plan (title, nodes, challenges, improvements, alternatives, Slack message) |
| 6 | Slack Review & Approve | Send plan to Slack; wait for Approve or Regenerate |
| 7 | Check Approval | Route: approved → Steps 8-9; regenerate → back to Step 5 |
| 8 | Archive to Sheets | Append approved row to mock Google Sheets CSV |
| 9 | Mark as Notified | Update task notes to "✅ Processed" |

## Notes

- **Google Tasks**, **Google Sheets**, and **Slack** operations are **mocked** (no credentials needed)
- **OpenAI API** is a **real call** using GPT-5.1 for n8n plan generation (Step 5 only)
- Approved plans archived to `results/outputs/archived_ideas.csv`
- Slack messages saved to `results/outputs/slack_message_*.json`
- Regeneration loop: up to 2 regeneration attempts per idea before skipping
- Set `SLACK_AUTO_APPROVE=false` in `.env` to simulate rejection and test regeneration

## Setup

```bash
cp .env.template .env
# Edit .env with your OpenAI API key
uv sync
```

## Run Server

```bash
uv run python mcp_server/server.py
```

## Run Workflow

```bash
uv run python run_workflow.py
```

## Run Tests

```bash
uv run python -m pytest tests/test_tools.py -v
```

## Project Structure

```
mcp_project70/
├── mcp_server/
│   ├── server.py                   # MCP Server (7 tools)
│   └── tools/
│       ├── tasks_tools.py          # Google Tasks mock (Steps 2, 3, 9)
│       ├── ai_tools.py             # GPT Solution Architect (Step 5)
│       ├── slack_tools.py          # Slack review mock (Steps 6, 7)
│       ├── sheets_tools.py         # Google Sheets archive mock (Step 8)
│       └── utils/log_decorator.py
├── tests/test_tools.py
├── run_workflow.py                 # Steps 1-9 with regeneration loop
├── workflow.json
└── logs/ results/
```
