# AI-powered Leads-to-Sales Outreach Automation — MCP Project

Converts the n8n workflow **"Leads To Sales"** into a fully self-contained
MCP (Model Context Protocol) project backed by FastMCP.

## What it does

| Step | n8n Node | MCP Tool | Notes |
|------|----------|----------|-------|
| 1 | Get row(s) in sheet | `get_leads` | Google Sheets → local CSV |
| 2 | If1 (filter empty research) | `filter_unresearched_leads` | Only process new leads |
| 3 | Search Internet1 (Tavily) | `search_internet` | Tavily → mock search results |
| 4 | Company Research1 (AI Agent) | `research_company` | Groq → OpenAI-compatible LLM |
| 5 | updateDescription | `update_lead_research` | Google Sheets → CSV update |
| 6 | updateStatus | `update_lead_status` | Google Sheets → CSV update |
| 7 | getTemplate | `get_email_template` | Google Sheets → local CSV |
| 8 | getService | `get_services` | Google Sheets → local CSV |
| 9 | Search Internet2 (Tavily) | `search_internet` | Tavily → mock search results |
| 10 | AI Sales Assistant (AI Agent) | `draft_sales_email` | Groq → OpenAI-compatible LLM |
| 11 | draftEmail | `save_email_draft` | Google Sheets → CSV update |
| 12 | Code (URL encode) | `encode_company_url` | JS Code node → Python |
| 13 | inputLink | `save_send_link` | Google Sheets → CSV update |

**Mock mode:** Google Sheets and Tavily search are replaced with local CSV files
and simulated search results. Only the OpenAI-compatible LLM API is called for
real (company research agent + email drafting agent).

---

## Project structure

```
mcp_project58/
├── README.md
├── .env                           # API keys and config
├── .env.template
├── pyproject.toml                 # uv-managed dependencies
├── workflow.json                  # workflow step configuration
├── run_workflow.py                # main workflow runner (fastmcp Client)
│
├── data/
│   ├── leads.csv                  # leads data (mock Google Sheets)
│   ├── templates.csv              # email templates by stage
│   └── services.csv               # products/services list
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                  # FastMCP server, registers all 12 tools
│   └── tools/
│       ├── __init__.py
│       ├── leads_tools.py         # get_leads, filter, update, save, encode
│       ├── research_tools.py      # search_internet, research_company
│       ├── email_tools.py         # draft_sales_email
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
    │   └── email_drafts.json      # generated email drafts
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
- Read leads from `data/leads.csv`
- Filter only unresearched leads
- For each lead: AI research → save results → draft personalized email → save draft
- Write email drafts to `results/outputs/email_drafts.json`
- Write run metrics to `results/metrics/run_metrics.json`

### 4. Run tests

```bash
uv run python -m pytest tests/ -v
```

---

## Configuration

Edit `.env` (copied from `.env.template`):

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI-compatible API key |
| `OPENAI_BASE_URL` | Yes | API base URL |
| `OPENAI_MODEL` | No | Model name (default: `gpt-5.1`) |
| `LEADS_CSV_PATH` | No | Path to leads CSV (default: `data/leads.csv`) |
| `TEMPLATES_CSV_PATH` | No | Path to templates CSV (default: `data/templates.csv`) |
| `SERVICES_CSV_PATH` | No | Path to services CSV (default: `data/services.csv`) |

### Adding leads

Edit `data/leads.csv` to add new leads:

```csv
Nama,Jabatan,Email,Perusahaan,Hasil Riset,Status,Send Email Perkenalan,Kirim email
John Doe,VP Engineering,EMAIL_PLACEHOLDER,Company X,,,,
```

---

## Key design notes

- **Google Sheets mocked:** All sheet operations use local CSV files.
- **Tavily search mocked:** Internet search returns pre-configured results for
  known Indonesian companies (Bank BCA, Telkom, Bank Mandiri) and generic
  results for unknown queries.
- **Two AI agents:** Company Research agent analyzes companies and identifies
  AI opportunities; Sales Assistant agent drafts personalized emails.
- **Human-in-the-loop:** The workflow generates a send-email link (Step 13)
  that acts as a manual trigger before sending.
- **stdio purity:** `server.py` uses file-only logging to avoid breaking MCP.
