# What is this?
Polymarket Historical Price Collector. Converts an n8n workflow into an MCP project that collects historical price data from Polymarket Up/Down serial markets (e.g. Bitcoin hourly). Phase 1 fetches all event IDs from a series slug via public Polymarket API. Phase 2 batch-processes closed events, fetches price history, and stores results locally (mock Supabase).

# How to run?

1. Install dependencies:
```bash
uv sync
```

2. **Important: Clean data before running** (the workflow uses local JSON files as storage; previous runs will mark events as processed):
```bash
rm -rf data/
```

3. Run the workflow:
```bash
uv run python run_workflow.py
```

4. Run tests:
```bash
uv run python -m pytest tests/test_tools.py -v
```

# Notes
- Polymarket API is public, no API keys needed.
- Supabase and n8n data tables are replaced by local JSON files in `data/`.
- The series contains thousands of events; the workflow limits to 20 closed events and processes 1 in Phase 2 for practical execution time.
- To re-run the full workflow from scratch, always `rm -rf data/` first.

# Workflow Steps
| Step | Tool | Description |
|------|------|-------------|
| 1 | (trigger) | User provides Polymarket market slug |
| 2 | find_event_id_from_slug | Find event ID from slug via gamma-api |
| 3 | find_series_id_from_event | Find series ID from event |
| 4 | find_all_events_for_series | Find all events in the series |
| 5 | split_events | Split events array into records |
| 6 | register_event | Register events into local event table |
| 7 | fetch_unprocessed_events | Fetch unprocessed events (limit 1) |
| 8 | fetch_up_down_tokens | Fetch UP/DOWN token IDs and end time |
| 9 | store_tokens_and_endtime | Extract and store tokens in event table |
| 10 | check_market_closed | Check if market is closed (skip if open) |
| 11 | convert_endtime_to_unix | Convert end time to Unix timestamp |
| 12 | set_start_time | Set start time = end time - 1 hour |
| 13 | fetch_price_history | Fetch price history for UP token |
| 14 | split_prices_and_timestamps | Split into price and timestamp arrays |
| 15 | store_in_supabase | Store price data locally (mock Supabase) |
| 16 | mark_event_processed | Mark event as processed |

# The architecture
```txt
mcp_project64/
├── README.md
├── .env.template
├── mcp_server/
│   ├── __init__.py
│   ├── server.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── polymarket_api_tools.py
│   │   ├── data_tools.py
│   │   ├── storage_tools.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── log_decorator.py
│   │       └── mock_storage.py
├── tests/
│   ├── __init__.py
│   └── test_tools.py
├── data/                              # Local JSON storage (auto-created)
│   ├── event_table.json               # Event metadata
│   └── supabase_table.json            # Price data (mock Supabase)
├── logs/
│   ├── server.log
│   └── workflow.log
├── results/
│   ├── outputs/
│   └── metrics/
├── run_workflow.py
├── workflow.json
├── pyproject.toml
├── uv.lock
├── .venv
└── .python-version
```
