# Docker Management Bot via Telegram

MCP project converted from n8n workflow. Monitors Docker containers via Uptime Kuma webhooks and provides Telegram-based management: AI log analysis, container restart, status check, and image updates.

## Workflow Paths

| Path | Trigger | Steps | Description |
|------|---------|-------|-------------|
| A | Uptime Kuma Webhook | 1-4 | Heartbeat monitor → OK/ERROR Telegram alert |
| B | Telegram `<service> logs` | 5-10 | Fetch logs → GPT analysis → Telegram |
| C | Telegram `<service> restart` | 11-15 | Restart container → success/fail notification |
| D | Telegram `status` | 16-17 | `docker ps` → Telegram |
| E | Telegram `update` | 18-21 | Update all docker-compose images → summary |

## Notes

- All SSH/Docker/Telegram operations are **mocked** (no real server needed)
- OpenAI API is a **real call** using GPT-5.1 for log analysis (Path B only)
- Mock Docker logs available for: `nginx`, `postgres`, `redis`

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

## Run Workflow (all 5 paths)

```bash
uv run python run_workflow.py
```

## Run Tests

```bash
uv run python -m pytest tests/test_tools.py -v
```

## Project Structure

```
mcp_project69/
├── mcp_server/
│   ├── server.py               # MCP Server (20 tools)
│   └── tools/
│       ├── webhook_tools.py    # Uptime Kuma heartbeat (Steps 1-4)
│       ├── command_tools.py    # Message parse/route/update parse (Steps 5-6, 20)
│       ├── docker_tools.py     # Docker operations via SSH mock (Steps 7,12,13,16,19)
│       ├── ai_tools.py         # GPT log analysis (Step 9)
│       ├── notification_tools.py # All Telegram sends mock (Steps 3,4,8,10,11,14,15,17,18,21)
│       └── utils/log_decorator.py
├── tests/test_tools.py
├── run_workflow.py             # All 5 paths, steps 1-21
├── workflow.json
└── logs/ results/
```
