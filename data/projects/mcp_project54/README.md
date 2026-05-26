# Smart Inventory Replenishment & Auto-Purchase Orders

MCP project converted from n8n workflow. Runs on a schedule to check warehouse stock levels, analyze sales velocity, use GPT AI to forecast demand per product, and automatically generate purchase orders for items that need restocking. POs are sent to suppliers, logged in ERP, saved to a SQLite database, and emailed to the procurement team.

## Workflow Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | Schedule Trigger | Fires every 6 hours to start the cycle |
| 2 | Fetch Current Inventory | Retrieve stock levels from warehouse (mock) |
| 3 | Fetch Sales Velocity | Retrieve 30-day sales data (mock) |
| 4 | Merge Inventory & Sales Data | Join records by product_id |
| 5 | AI Demand Forecasting | GPT-5.1 forecasts demand per product |
| 6 | Parse AI Response | Extract structured forecast + merge with product data |
| 7 | Filter: Reorder Needed | Pass only items where `should_reorder=true` |
| 8 | Create Purchase Order | Generate PO with unique number, costs, delivery date |
| 9 | Send PO to Supplier | POST PO to supplier API (mock) |
| 10 | Log to ERP System | Record PO in ERP system (mock JSON) |
| 11 | Save to Database | Insert PO into SQLite database |
| 12 | Send Notification Email | Email procurement team (mock) |

## Notes

- **Warehouse API**, **Sales API**, **Supplier API**, **ERP**, and **Email** are all **mocked** (no credentials needed)
- Mock inventory has 5 products: Widget Pro, Gadget Ultra, Component Basic, Device Elite, Part Standard
- **OpenAI GPT-5.1** is used for real AI demand forecasting (requires API key)
- Supplier orders saved to `results/outputs/supplier_orders.json`
- ERP log saved to `results/outputs/erp_log.json`
- Email log saved to `results/outputs/email_log.json`
- Purchase orders saved to `results/outputs/purchase_orders.db` (SQLite)

## Setup

```bash
cp .env.template .env
# Edit .env and fill in your OPENAI_API_KEY
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
mcp_project54/
├── mcp_server/
│   ├── server.py                  # MCP Server (12 tools)
│   └── tools/
│       ├── inventory_tools.py     # Schedule trigger + warehouse/sales fetch (Steps 1-3)
│       ├── data_tools.py          # Merge, parse AI response, filter, create PO (Steps 4, 6-8)
│       ├── ai_tools.py            # GPT-5.1 demand forecasting (Step 5)
│       ├── supplier_tools.py      # Supplier API mock (Step 9)
│       ├── erp_tools.py           # ERP log, SQLite DB, email notification (Steps 10-12)
│       └── utils/log_decorator.py
├── tests/test_tools.py            # 35 tests
├── run_workflow.py                # Full 12-step pipeline for 5 products
├── workflow.json
├── .env.template
└── logs/ results/
```
