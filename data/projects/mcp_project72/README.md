# AI Hotel Receptionist via WhatsApp

MCP project converted from n8n workflow. An AI-powered hotel receptionist that receives WhatsApp messages from guests, uses Redis to load-balance between two GPT model slots, runs a GPT agent with SQL (MySQL) and pricing (Google Sheets) tools to answer hotel queries, and replies via WhatsApp.

## Workflow Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | WhatsApp Trigger | Receive guest message from WhatsApp |
| 2 | Check Message | Validate it is a text message; skip otherwise |
| 3 | Check User Number | Redis GET — look up guest's model assignment |
| 4 | Model Decider | Alternate model index 0↔1 for load balancing |
| 5 | Store User Number | Redis SET — persist new model index (TTL=3600s) |
| 6 | AI Agent | GPT hotel agent with SQL + pricing tools; per-user memory |
| 7 | Send Message | Mock WhatsApp reply to guest |

## AI Agent Tools

The GPT agent (Step 6) has access to:
- **execute_sql_query** — runs read-only SELECT queries on the mock hotel SQLite database (rooms, guests, bookings tables)
- **get_room_pricing** — returns pricing data from mock Google Sheets (weekday/weekend rates, extra bed, breakfast)

Security: only SELECT statements are allowed; INSERT/UPDATE/DELETE/DROP are blocked.

## Hotel Mock Data

- **10 rooms**: Standard, Deluxe, Suite, Family across 3 floors
- **5 guests** with realistic profiles
- **5 bookings** with various statuses (confirmed, checked_in, checked_out)

## Notes

- **WhatsApp**, **Redis**, **MySQL**, and **Google Sheets** are **mocked** (no credentials needed)
- **OpenAI GPT** is a **real call** using GPT-5.1 with function calling for tool use
- WhatsApp replies saved to `results/outputs/whatsapp_reply_*.json`
- Conversation memory persisted to `results/outputs/memory_<wa_id>.json`

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
mcp_project72/
├── mcp_server/
│   ├── server.py                  # MCP Server (9 tools)
│   └── tools/
│       ├── whatsapp_tools.py      # WhatsApp mock (Steps 1, 2, 7)
│       ├── redis_tools.py         # Redis mock (Steps 3, 5)
│       ├── model_tools.py         # Model alternation (Step 4)
│       ├── hotel_data_tools.py    # SQLite + pricing mock (Step 6 tools)
│       ├── ai_tools.py            # GPT agent with function calling (Step 6)
│       └── utils/log_decorator.py
├── tests/test_tools.py            # 22 tests
├── run_workflow.py                # Steps 1-7, multi-session demo
├── workflow.json
└── logs/ results/
```
