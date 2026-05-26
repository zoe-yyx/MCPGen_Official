# What is this?
AI Trading Alert Bot. Converts an n8n workflow into an MCP project that monitors cryptocurrency and stock markets, calculates technical indicators, uses AI for buy/sell signal prediction, and sends multi-channel alerts (Slack, Email, SMS — all mock). Trade signals are stored locally (mock PostgreSQL).

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
| 1 | fetch_crypto_prices | Fetch crypto prices from CoinGecko (mock) |
| 2 | fetch_stock_prices | Fetch stock prices from Alpha Vantage (mock) |
| 3 | combine_market_data | Combine crypto and stock data |
| 4 | calculate_technical_indicators | Calculate RSI, MACD, Bollinger Bands, etc. |
| 5 | call_ai_signal_prediction | Call AI model for signal prediction |
| 6 | analyze_signals_confidence | Analyze AI signals and confidence score |
| 7 | validate_signal_filter | Filter signals by strength threshold |
| 8 | store_trade_signal | Store signal to PostgreSQL (mock local) |
| 9 | route_by_action | Route by signal action (buy/sell/hold) |
| 10 | generate_alert_message | Generate formatted alert message |
| 11 | send_slack_notification | Send Slack notification (mock) |
| 12 | send_email_alert | Send email alert (mock) |
| 13 | send_sms_alert | Send SMS alert via Twilio (mock) |
| 14 | log_trade_execution | Log trade execution result |

# The architecture
```txt
mcp_project63/
├── README.md
├── .env.template
├── mcp_server/
│   ├── __init__.py
│   ├── server.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── data_tools.py
│   │   ├── analysis_tools.py
│   │   ├── notification_tools.py
│   │   ├── storage_tools.py
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
