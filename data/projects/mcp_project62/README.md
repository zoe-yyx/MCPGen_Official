# What is this?
Daily Stock Monitor with AI Summary Email. Converts an n8n workflow into an MCP project that scrapes Financial Times for top US stocks (mock Bright Data), saves results to Google Sheets (mock local), aggregates data, generates an AI summary via LLM, and sends a daily email report (mock Gmail).

# How to run?

1. Install dependencies:
```bash
uv sync
```

2. Configure environment variables:
```bash
cp .env.template .env
# Edit .env and fill in API_KEY, BASE_URL, MODEL
```

3. Run the workflow:
```bash
uv run python run_workflow.py
```

4. Run tests:
```bash
uv run python -m pytest tests/test_tools.py -v
```

# Workflow Steps
| Step | Tool | Description |
|------|------|-------------|
| 1 | get_sample_data | Get sample stock ticker data |
| 2 | split_and_set_keywords | Split tickers and set search keywords |
| 3 | scrape_financial_times | Scrape Financial Times articles (mock) |
| 4 | get_scraping_progress | Check scraping job progress (mock) |
| 5 | get_snapshot_data | Get scraped snapshot data |
| 6 | save_to_sheets | Save data to Google Sheets (mock local) |
| 7 | aggregate_data | Aggregate scraped data |
| 8 | create_summary | Generate AI summary via LLM |
| 9 | send_email | Send summary email via Gmail (mock) |

# The architecture
```txt
mcp_project62/
├── README.md
├── .env.template
├── mcp_server/
│   ├── __init__.py
│   ├── server.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── data_tools.py
│   │   ├── scraping_tools.py
│   │   ├── analysis_tools.py
│   │   ├── notification_tools.py
│   │   └── utils/
│   │       └── log_decorator.py
├── tests/
│   ├── __init__.py
│   └── test_tools.py
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
