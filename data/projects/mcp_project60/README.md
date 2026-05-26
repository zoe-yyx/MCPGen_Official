# Multi-Asset Daily Market Snapshot — MCP Project

Converts the n8n workflow **"Multi-Asset Daily Snapshot"** into a fully self-contained
MCP (Model Context Protocol) project backed by FastMCP.

## What it does

| Step | n8n Node | MCP Tool | Notes |
|------|----------|----------|-------|
| 1 | Set Market Assets | `set_market_assets` | Configure asset groups |
| 2 | split assets & Symbols | `split_assets_symbols` | Comma-split into records |
| 3 | Fetch Asset Prices | `fetch_asset_price` | TwelveData → mock local data |
| 4 | Validate API Response | `validate_api_response` | Check status == "ok" |
| 4e | Log API Error + Alert | `log_api_error` + `send_error_alert` | Error CSV + mock Gmail |
| 5 | Normalize Market Data | `normalize_market_data` | Calc change%, trend |
| 6 | AI Market Insights (Groq) | `generate_market_insights` | Groq/Llama → gpt-4.1-mini |
| 7 | Parse AI Output | `parse_ai_output` | Extract sections via regex |
| 8 | Log Daily Market Report | `log_daily_report` | Google Sheets → local CSV |
| 9 | Send Today's Market Summary | `send_market_email` | Gmail → local text file |

**Mock mode:** TwelveData API is mocked with pre-configured price data.
Google Sheets and Gmail are simulated locally. The AI model (gpt-4.1-mini) is real.

---

## Project structure

```
mcp_project60/
├── README.md
├── .env                           # API keys and config
├── pyproject.toml                 # uv-managed dependencies
├── workflow.json                  # workflow step configuration
├── run_workflow.py                # main workflow runner (fastmcp Client)
│
├── data/
│   ├── reports.csv                # daily report log (auto-created)
│   └── errors.csv                 # error log (auto-created)
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                  # FastMCP server, registers 11 tools
│   └── tools/
│       ├── __init__.py
│       ├── market_tools.py        # Asset config, price fetching, normalization
│       ├── ai_tools.py            # AI insights generation, output parsing
│       ├── report_tools.py        # Logging, email notifications (mock)
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
    │   └── market_email.txt       # generated market report email
    └── metrics/
        └── run_metrics.json
```

---

## Quick start

```bash
# Install dependencies
uv sync

# Run the full workflow
uv run python run_workflow.py

# Run tests (no MCP server needed)
uv run pytest tests/ -v
```

---

## How it works

1. **Asset Configuration** — Defines 3 asset groups: Indices (SPY, QQQ, DIA), Forex (EUR/USD, USD/INR, GBP/USD, USD/JPY), Commodities (XAU/USD, USO)
2. **Symbol Splitting** — Breaks groups into 9 individual symbols
3. **Price Fetching** — Queries each symbol with rate-controlled batching (mock TwelveData)
4. **Validation** — Checks API response status; errors are logged and alerted
5. **Normalization** — Calculates open/close change %, determines bullish/bearish trend
6. **AI Analysis** — Sends normalized data to gpt-4.1-mini with a structured prompt for market insights
7. **Output Parsing** — Extracts: Market Summary, Key Movers, Risk Sentiment, Actionable Insight, Outlook
8. **Report Logging** — Appends structured report to CSV
9. **Email Delivery** — Saves formatted market email to local file

---

## External services

| Service | Purpose | Implementation |
|---------|---------|---------------|
| TwelveData API | Market price data | Mock with pre-configured prices |
| Groq (Llama 3.3 70B) | AI market analysis | Replaced with gpt-4.1-mini via OpenAI API |
| Google Sheets | Report + error logging | Local CSV files |
| Gmail | Email notifications | Local text files |

---

## API Configuration

The AI model uses gpt-4.1-mini via an OpenAI-compatible endpoint:
```
api_key: REDACTED_API_KEY
base_url: ENDPOINT_PLACEHOLDER
model: gpt-4.1-mini
```
