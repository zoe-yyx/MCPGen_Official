# WeChat Article Classifier & Summarizer — MCP Project

> Converted from n8n workflow: **"Classify and Summarize WeChat Articles to Google Sheets and Notion"**

## 📐 Architecture Overview

```
n8n Node                              → MCP Tool
────────────────────────────────────────────────────────────────────────
Read Initial Links (Sheets)           → tool_read_initial_links
Read RSS Links (Sheets)               → tool_read_rss_links
RSS Read                              → tool_rss_read
pubDate Processing (Set)              → tool_process_pubdate
IF (Filter by Date)                   → tool_filter_by_date
Filtered Data (Set passthrough)       → tool_set_filtered_data
Save Initial Data (Sheets)            → tool_save_initial_data
pubDate&link Only (Set projection)    → tool_extract_pubdate_link
Filter Unique Links (Code)            → tool_filter_unique_links
Restore Full Data with Code           → tool_restore_full_data
Clean HTML Content (Code)             → tool_clean_html_content
Relevance Classification (LangChain)  → tool_classify_relevance
Basic LLM Chain (LangChain)           → tool_summarize_article
Google Sheets – Add relevant article  → tool_save_relevant_article
Create a database page (Notion)       → tool_create_notion_page
```

### Workflow Steps

```
Step 1 – Data Input
  [Google Sheets] Read initial links  ──┐
  [Google Sheets] Read RSS feed URLs  ──┤
  [RSS Read] Fetch each feed           ─┘→ normalise pubDate

Step 2 – Deduplication
  Filter entries → last 10 days
  Save filtered entries → Sheets (Save Initial Links)
  Project to {pubDate, link}
  Merge with initial_links → filter unique (new articles only)
  Restore full RSS data for new links

Step 3 – Processing (per article)
  Clean HTML content
  Classify relevance (GPT-4.1-nano) → discard if not_relevant
  Summarize relevant articles (GPT-4.1-nano, Chinese, Slack format)

Step 4 – Output (per relevant article)
  Append to Google Sheets (Relevant Articles)
  Create Notion database page
```

## 📁 Project Structure

```
wechat_article_mcp/
├── .env.template                     # Environment variable template
├── .env                              # Your actual credentials (git-ignored)
├── README.md
├── pyproject.toml                    # uv-managed dependencies
├── workflow.json                     # Workflow configuration & step registry
├── run_workflow.py                   # Main workflow runner (FastMCP client)
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                     # FastMCP server – registers all tools
│   └── tools/
│       ├── __init__.py
│       ├── sheets_tools.py           # Google Sheets read/write tools
│       ├── rss_tools.py              # RSS feed fetch & parse
│       ├── processing_tools.py       # Date filter, dedup, HTML clean
│       ├── ai_tools.py               # Classification & summarization
│       ├── notion_tools.py           # Notion page creation
│       └── utils/
│           ├── __init__.py
│           └── logging_decorator.py  # setup_logging + log_tool_call decorator
├── tests/
│   ├── __init__.py
│   └── test_tools.py                 # Unit tests (no MCP required)
├── logs/
│   ├── server.log                    # MCP server log
│   └── workflow.log                  # Workflow execution log
└── results/
    ├── outputs/                      # JSON results per run
    └── metrics/                      # Reserved for metrics
```

## 🚀 Quick Start

### 1. Clone / enter the project directory

```bash
cd wechat_article_mcp
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

```bash
cp .env.template .env
# Edit .env and fill in your credentials:
# - AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY
# - GOOGLE_SERVICE_ACCOUNT_JSON  (or GOOGLE_TOKEN_JSON)
# - NOTION_TOKEN
```

### 4. Run in mock mode (no external APIs needed)

```bash
uv run python run_workflow.py --mock
```

This uses local mock data, calls the AI tools with mock responses, and
skips real Google Sheets / Notion writes.  Ideal for validating the
full pipeline end-to-end before connecting live credentials.

### 5. Run with real APIs

```bash
uv run python run_workflow.py
```

Results are saved to `results/outputs/workflow_result_real_<timestamp>.json`.

---

## 🔑 Credentials Setup

### Azure OpenAI

| Variable | Description |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | e.g. `ENDPOINT_PLACEHOLDER |
| `AZURE_OPENAI_API_KEY` | Your deployment API key |
| `AZURE_OPENAI_API_VERSION` | Default: `2024-12-01-preview` |
| `AZURE_OPENAI_CLASSIFICATION_MODEL` | Default: `gpt-4.1-nano` |
| `AZURE_OPENAI_SUMMARY_MODEL` | Default: `gpt-4.1-nano` |

### Google Sheets

Preferred: **Service Account** (works in both local and CI environments).

1. Create a Service Account in Google Cloud Console.
2. Grant it **Editor** access to the target spreadsheet.
3. Download the JSON key, paste it (single line) as `GOOGLE_SERVICE_ACCOUNT_JSON`.

Alternative: **OAuth2 token** — set `GOOGLE_TOKEN_JSON` instead.

| Variable | Description |
|---|---|
| `GOOGLE_SPREADSHEET_ID` | The 44-char ID from the spreadsheet URL |
| `SHEET_SAVE_INITIAL` | Sheet storing initial/processed links (default: `Save Initial Links`) |
| `SHEET_READ_RSS` | Sheet listing RSS feed URLs (default: `Read RSS Links`) |
| `SHEET_RELEVANT` | Output sheet for relevant articles (default: `Relevant Articles`) |

#### Expected sheet layouts

**Read RSS Links** (columns: `rss_feed_url`, optional others):
| rss_feed_url |
|---|
| ENDPOINT_PLACEHOLDER |

**Save Initial Links** (columns: `pubDate`, `title`, `link`):
| pubDate | title | link |
|---|---|---|
| 2025-04-10T08:00:00+00:00 | Article A | ENDPOINT_PLACEHOLDER |

**Relevant Articles** (columns: `article_url`, `summarized`, `title`, `summary`, `fetched_at`, `publish_date`):
Auto-created by the workflow.

### Notion

1. Create an **Internal Integration** at ENDPOINT_PLACEHOLDER
2. Copy the token (`secret_…`) → `NOTION_TOKEN`.
3. Share your database with the integration.
4. Copy the database UUID → `NOTION_DATABASE_ID`.

The database must have these properties:
| Property | Type |
|---|---|
| `article_url` | Title |
| `summary` | Rich text |
| `fetched_at` | Rich text |

---

## 🧪 Running Tests

```bash
# All tests (no external APIs required)
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ -v --tb=short
```

Tests mock all external API calls (Google Sheets, Azure OpenAI, Notion, feedparser).

---

## 📊 Logs

| File | Contents |
|---|---|
| `logs/server.log` | MCP server tool call traces (DEBUG level) |
| `logs/workflow.log` | Workflow step-by-step execution (INFO + console) |

Logs are written in append mode.  Rotate or clear them manually as needed.

---

## ⚙️ Customising Classification Topics

Edit the classification descriptions in `mcp_server/tools/ai_tools.py`:

```python
_RELEVANT_DESCRIPTION = (
    "Articles related to 欧阳良宜, 读书笔记，AI in these fields."
)
_NOT_RELEVANT_DESCRIPTION = (
    "Articles not directly related to 欧阳良宜, 招生, 超级个体 in these fields."
)
```

Or pass custom descriptions directly to `tool_classify_relevance()`:

```python
result = await call(
    client,
    "tool_classify_relevance",
    title=title,
    cleaned_content=content,
    relevant_description="Articles about machine learning and LLMs.",
    not_relevant_description="Articles about sports or entertainment.",
)
```

---

## 🔧 Extending the Project

To add a new output destination (e.g. Slack):

1. Create `mcp_server/tools/slack_tools.py` with a `tool_post_to_slack()` function.
2. Register it in `mcp_server/server.py`: `mcp.tool()(tool_post_to_slack)`.
3. Add a call in `run_workflow.py` inside the Step 4 output loop.
4. Add the step to `workflow.json`.