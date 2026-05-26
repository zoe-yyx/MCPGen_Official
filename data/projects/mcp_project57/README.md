# AI-powered Concert Ticket Validation & Fan Experience Orchestration — MCP Project

Converts the n8n workflow **"AI-powered concert ticket validation and fan
experience orchestration"** into a fully self-contained MCP (Model Context
Protocol) project backed by FastMCP.

## What it does

| Step | n8n Node | MCP Tool | Notes |
|------|----------|----------|-------|
| 1 | Ticket Booking Webhook | `receive_booking` | Webhook → local JSON file |
| 2 | Workflow Configuration | `get_workflow_config` | Set node → config dict |
| 3 | Fetch Inventory Data | `fetch_inventory` | HTTP Request → mock inventory |
| 4 | Prepare Validation Input | `prepare_validation_input` | Set node → combine data |
| 5 | Ticket Validation Agent | `validate_ticket` | AI Agent + OpenAI |
| 6 | Route by Risk Level | `route_by_risk_level` | Switch node |
| 7 | Fan Experience Orchestration Agent | `orchestrate_fan_experience` | AI Agent + OpenAI |
| 8 | Update Ticketing System | `update_ticketing_system` | HTTP POST → mock |
| 8b | Send Confirmation Email | `send_confirmation_email` | Gmail → local file |
| 9 | Alert Operations Team | `alert_operations_team` | Slack → local JSONL |
| 10 | Log to Audit Trail | `log_audit_trail` | Google Sheets → local CSV |

**Mock mode:** Webhook, inventory API, ticketing API, Gmail, Slack, and Google
Sheets are all replaced with local file operations. Only the OpenAI-compatible
LLM API is called for real (two AI agents).

---

## Project structure

```
mcp_project57/
├── README.md
├── .env                           # API keys and config
├── .env.template                  # copy to .env and fill credentials
├── pyproject.toml                 # uv-managed dependencies
├── workflow.json                  # workflow step configuration
├── run_workflow.py                # main workflow runner (fastmcp Client)
│
├── data/
│   └── sample_booking.json        # sample booking request (mock webhook)
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                  # FastMCP server, registers all 11 tools
│   └── tools/
│       ├── __init__.py
│       ├── booking_tools.py       # receive_booking, get_workflow_config, fetch_inventory, prepare_validation_input
│       ├── validation_tools.py    # validate_ticket, route_by_risk_level
│       ├── orchestration_tools.py # orchestrate_fan_experience, update_ticketing_system
│       ├── notification_tools.py  # send_confirmation_email, alert_operations_team, log_audit_trail
│       └── utils/
│           ├── __init__.py
│           └── log_decorator.py
│
├── tests/
│   ├── __init__.py
│   └── test_tools.py
│
├── logs/
│   ├── server.log
│   └── workflow.log
│
└── results/
    ├── outputs/
    │   ├── email_BK-*.json        # confirmation emails
    │   ├── alerts.jsonl           # high-risk alert history
    │   └── audit_trail.csv        # audit trail log
    └── metrics/
        └── run_metrics.json       # per-run summary
```

---

## Quick start

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp .env.template .env
# Edit .env and fill in your API key
```

### 3. Run the workflow

```bash
uv run python run_workflow.py
```

This will:
- Load a sample booking from `data/sample_booking.json`
- Run AI-powered ticket validation (fraud detection, risk scoring)
- Route by risk level (low/medium → orchestrate; high/critical → alert)
- Send confirmation email or alert operations team
- Log all outcomes to audit trail CSV

### 4. Run tests

```bash
uv run python -m pytest tests/ -v
```

---

## Configuration

Edit `.env` (copied from `.env.template`):

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI-compatible API key for AI agent calls |
| `OPENAI_BASE_URL` | Yes | OpenAI-compatible API base URL |
| `OPENAI_MODEL` | No | Model name (default: `gpt-5.1`) |
| `SAMPLE_BOOKING_PATH` | No | Path to booking JSON (default: `data/sample_booking.json`) |

### Customizing the booking

Edit `data/sample_booking.json` to test different scenarios:
- Change `ticketQuantity` to exceed `maxTicketsPerCustomer` (8) for fraud detection
- Change `totalAmount` to mismatch tier pricing for pricing validation
- Remove consent flags to trigger consent check failures

---

## Key design notes

- **Two AI agents**: The Ticket Validation Agent performs risk scoring and fraud
  detection; the Fan Experience Orchestration Agent coordinates downstream
  workflows (confirmations, loyalty, refunds, escalations).
- **Risk routing**: LOW/MEDIUM risk → auto-approve + orchestrate; HIGH/CRITICAL
  → alert operations team for manual review.
- **All external services mocked**: Inventory API, ticketing API, Gmail, Slack,
  and Google Sheets are replaced with local file operations.
- **stdio purity**: `server.py` uses file-only logging (`console_output=False`)
  to avoid breaking the MCP JSON-RPC protocol.
- **Tool results**: FastMCP returns `result.content[0].text` as a JSON string;
  `run_workflow.py` uses `json.loads()` to parse structured results.
