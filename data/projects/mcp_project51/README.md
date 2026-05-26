# User Review Aggregation — MCP Project

Converts the n8n workflow **"User Review Aggregation"** into a fully self-contained
MCP (Model Context Protocol) project backed by FastMCP.

## What it does

| Step | n8n Node | MCP Tool | Notes |
|------|----------|----------|-------|
| 1 | Get row(s) in sheet | `tool_get_urls_from_csv` | Google Sheets → local CSV |
| 2 | Decodo | `tool_scrape_amazon_reviews` | Amazon review scraper |
| 3 | Code in JavaScript | `tool_format_reviews` | Raw JSON → clean text |
| 4 | Sentiment Analyzer | `tool_analyze_sentiment` | Gemini → Azure OpenAI |
| 5 | Store to Sheet | `tool_store_result_to_csv` | Google Sheets → local CSV |
| 6 | Summarize Reviews | `tool_summarize_reviews` | chainSummarization → Azure OpenAI |
| 7 | Alert Group (Telegram) | `tool_send_alert` | Telegram optional; always logs |

**Mock mode (default):** the entire workflow runs without any API keys.
All external services are simulated locally.

---

## Project structure

```
mcp_project_user_review/
├── README.md
├── .env.template                  # copy to .env and fill credentials
├── pyproject.toml                 # uv-managed dependencies
├── workflow.json                  # workflow step configuration
├── run_workflow.py                # main workflow runner (fastmcp Client)
│
├── data/
│   └── urls.csv                   # product URLs to process (auto-created)
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                  # FastMCP server, registers all @mcp.tool()
│   └── tools/
│       ├── __init__.py
│       ├── scraper_tools.py       # tool_scrape_amazon_reviews, tool_format_reviews
│       ├── ai_tools.py            # tool_analyze_sentiment, tool_summarize_reviews
│       ├── storage_tools.py       # tool_get_urls_from_csv, tool_store_result_to_csv, tool_send_alert
│       └── utils/
│           ├── __init__.py
│           └── logging_decorator.py
│
├── tests/
│   ├── __init__.py
│   └── test_tools.py
│
├── logs/
│   ├── server.log                 # MCP server logs (file-only, never stdout)
│   └── workflow.log               # Workflow run logs
│
└── results/
    ├── outputs/
    │   ├── review_aggregations.csv  # stored results
    │   └── alerts.jsonl             # alert history
    └── metrics/
        └── run_metrics.json         # per-run summary
```

---

## Quick start

### 1. Install dependencies

```bash
uv sync
```

### 2. Run in mock mode (no credentials needed)

```bash
uv run python run_workflow.py
```

This will:
- Auto-create `data/urls.csv` with 3 sample Amazon URLs
- Run the full pipeline with synthetic data
- Write results to `results/outputs/review_aggregations.csv`
- Write alerts to `results/outputs/alerts.jsonl`
- Write metrics to `results/metrics/run_metrics.json`

### 3. Run with real APIs

```bash
cp .env.template .env
# Edit .env and fill in your credentials
uv run python run_workflow.py --real-api
```

### 4. Run tests

```bash
uv run python -m pytest tests/ -v
```

---

## Configuration

Edit `.env` (copied from `.env.template`):

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Real mode | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Real mode | Azure OpenAI API key |
| `AZURE_OPENAI_API_VERSION` | Real mode | e.g. `2024-02-01` |
| `AZURE_SENTIMENT_DEPLOYMENT` | Real mode | e.g. `gpt-4o-mini` |
| `AZURE_SUMMARY_DEPLOYMENT` | Real mode | e.g. `gpt-4o` |
| `DECODO_API_KEY` | Real mode | Decodo scraper API key |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Optional | Telegram chat/group ID |
| `URL_CSV_PATH` | Optional | Default: `data/urls.csv` |
| `RESULTS_CSV_PATH` | Optional | Default: `results/outputs/review_aggregations.csv` |

### Adding product URLs

Edit `data/urls.csv`:

```csv
url
ENDPOINT_PLACEHOLDER
ENDPOINT_PLACEHOLDER
```

---

## Key design notes

- **stdio purity**: `server.py` uses file-only logging (`console_output=False`).
  Any stdout/stderr from the server breaks the MCP JSON-RPC protocol.
- **No external accounts required in mock mode**: Google Sheets and Telegram
  are replaced with local CSV files and log/JSONL files respectively.
- **Telegram is fully optional**: alerts are always written to `logs/server.log`
  and `results/outputs/alerts.jsonl` even without Telegram credentials.
- **Tool results**: FastMCP returns `result.content[0].text` as a JSON string;
  `run_workflow.py` always calls `json.loads()` to parse it.