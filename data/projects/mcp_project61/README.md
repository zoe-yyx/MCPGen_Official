# What is this?
Gold vs Equity Performance Comparison Tracker. Converts an n8n workflow into an MCP project that automates financial performance analysis between gold and equity markets. Fetches historical price data, calculates performance metrics, generates AI investment insights, produces comparison charts, and sends report/alert emails (mock).

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
| 1 | set_analysis_parameters | Set date range and comparison parameters |
| 2 | fetch_gold_prices | Fetch gold price data (mock) |
| 3 | fetch_equity_prices | Fetch equity/S&P500 price data (mock) |
| 4 | merge_market_data | Merge gold and equity datasets |
| 5 | calculate_performance_metrics | Calculate returns, volatility, etc. |
| 6 | generate_chart | Generate comparison chart data |
| 7 | generate_ai_investment_insights | Call AI model for analysis |
| 8 | parse_ai_output | Parse AI response into structured data |
| 9 | combine_ai_chart_data | Combine AI insights with chart data |
| 10 | generate_final_report | Generate final HTML/text report |
| 11 | check_performance_gap | Check if gap exceeds alert threshold |
| 12 | send_report_email | Send regular report email (mock) |
| 13 | send_alert_email | Send alert email if gap is large (mock) |
| 14 | store_report_history | Store report to local history |

# The architecture
```txt
mcp_project61/
├── README.md
├── .env.template
├── mcp_server/
│   ├── __init__.py
│   ├── server.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── data_tools.py
│   │   ├── analysis_tools.py
│   │   ├── report_tools.py
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
