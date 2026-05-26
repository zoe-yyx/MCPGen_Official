# Chat with PDF/MD/Text Files using GraphRAG — MCP Project

Converts the n8n workflow **"Chat with PDF / MD / Text Files using GraphRAG
(no vector store needed)"** into a fully self-contained MCP (Model Context
Protocol) project backed by FastMCP.

## What it does

| Step | n8n Node | MCP Tool | Notes |
|------|----------|----------|-------|
| 1 | Search Google Drive | `search_local_files` | Google Drive → local folder |
| 2 | Retrieve File | `retrieve_file` | Google Drive download → local read |
| 3 | Switch (MIME type) | `detect_file_type` | Route by file type |
| 4 | Extract from PDF/Text/MD | `extract_pdf_text` / `extract_text_file` / `extract_markdown_file` | Text extraction |
| 5 | Map PDF to Text | `map_to_text` | Normalize whitespace |
| 6 | InfraNodus Save to Graph | `save_to_graph` | InfraNodus API → local JSON store |
| 7 | Simple Memory (clear) | `clear_memory` | Reset conversation buffer |
| 8 | AI Agent + OpenAI + KB | `chat_with_knowledge_base` | InfraNodus GraphRAG → local keyword retrieval + OpenAI |

**Mock mode:** Google Drive and InfraNodus are replaced with local file
operations. Only the OpenAI-compatible LLM API is called for real.

---

## Project structure

```
mcp_project56/
├── README.md
├── .env                           # API keys and config
├── .env.template                  # copy to .env and fill credentials
├── pyproject.toml                 # uv-managed dependencies
├── workflow.json                  # workflow step configuration
├── run_workflow.py                # main workflow runner (fastmcp Client)
│
├── data/                          # documents to ingest (mock Google Drive)
│   ├── sample.txt
│   └── sample.md
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                  # FastMCP server, registers all tools
│   └── tools/
│       ├── __init__.py
│       ├── file_tools.py          # search, retrieve, detect, extract, map
│       ├── graph_tools.py         # save_to_graph, query_knowledge_base
│       ├── chat_tools.py          # chat_with_knowledge_base, clear_memory
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
    │   ├── graph_store.json       # local graph knowledge base
    │   └── chat_results.json      # chat Q&A results
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
- Scan `data/` folder for PDF/MD/TXT files
- Extract text and save to local graph store (`results/outputs/graph_store.json`)
- Chat with the knowledge base using the LLM
- Write chat results to `results/outputs/chat_results.json`
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
| `OPENAI_API_KEY` | Yes | OpenAI-compatible API key for LLM calls |
| `OPENAI_BASE_URL` | Yes | OpenAI-compatible API base URL |
| `OPENAI_MODEL` | No | Model name (default: `gpt-5.1`) |
| `DATA_FOLDER` | No | Path to document folder (default: `data`) |
| `GRAPH_STORE_PATH` | No | Path to graph store JSON (default: `results/outputs/graph_store.json`) |

### Adding documents

Place your PDF, Markdown, or plain text files in the `data/` folder:

```
data/
├── report.pdf
├── notes.md
└── article.txt
```

---

## Key design notes

- **Google Drive mocked:** files are read from a local `data/` folder instead of
  calling the Google Drive API.
- **InfraNodus mocked:** the graph knowledge base is stored as a local JSON file
  with keyword-based retrieval, replacing the InfraNodus HTTP API.
- **OpenAI API is real:** the chat tool calls an OpenAI-compatible endpoint
  (configurable via `OPENAI_BASE_URL`) for LLM responses.
- **Conversation memory:** a simple buffer window keeps chat history across
  multiple questions within a single workflow run.
- **Tool results:** FastMCP returns `result.content[0].text` as a JSON string;
  `run_workflow.py` uses `json.loads()` to parse structured results.
