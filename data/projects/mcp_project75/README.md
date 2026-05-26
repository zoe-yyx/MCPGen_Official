# What is this?
DocAgent — AI-powered legal document generation from templates. Converts an n8n LangChain agent workflow into an MCP project. A chat-based agent helps users select a document template, collects required placeholder values through conversation, and generates a filled document. Google Drive/Docs and Apps Script are replaced by local JSON template files and Python fill logic.

# How to run?

1. Install dependencies:
```bash
uv sync
```

2. Configure environment variables:
```bash
cp .env.template .env
# Edit .env: fill in API_KEY, BASE_URL, MODEL
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
| 1 | list_templates | List all available templates (mock Google Drive) |
| 2 | get_template_metadata | Get placeholders and conditionals for selected template |
| 3 | verify_user_choice | LLM verifies template name-ID match |
| 4 | get_template_metadata (renew) | Re-fetch latest metadata after verification |
| 5 | format_user_data | LLM formats user answers into structured data dict |
| 6 | copy_template | Copy template to generated folder |
| 7 | fill_document | Replace placeholders and process conditional blocks |
| 8 | generate_download_link | Generate local download path for filled document |

# Notes
- All Google services (Drive, Docs, Apps Script) are mocked locally in `data/`.
- Templates use `{{PLACEHOLDER}}` syntax and `[[FLAG:START]]...[[FLAG:END]]` for conditional blocks.
- Two sample templates are included: `SATIŞ SÖZLEŞMESİ` (sales contract) and `KİRA SÖZLEŞMESİ` (rental agreement).
- Generated documents are saved as `.txt` files in `data/generated/`.
- Conversation memory is in-process (reset between runs).

# The architecture
```txt
mcp_project75/
├── README.md
├── .env.template
├── mcp_server/
│   ├── __init__.py
│   ├── server.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── template_tools.py       # list, metadata, copy, fill, download link
│   │   ├── doc_process_tools.py    # verify choice, format data, JSON parsing
│   │   ├── agent_tools.py          # LLM DocAgent conversation
│   │   └── utils/
│   │       └── log_decorator.py
├── tests/
│   ├── __init__.py
│   └── test_tools.py
├── data/
│   ├── templates/                  # Mock Google Drive templates (JSON)
│   │   ├── template_catalog.json
│   │   ├── tpl_001.json            # SATIŞ SÖZLEŞMESİ
│   │   └── tpl_002.json            # KİRA SÖZLEŞMESİ
│   └── generated/                  # Generated filled documents
├── logs/
│   ├── server.log
│   └── workflow.log
├── results/
│   └── outputs/
├── run_workflow.py
├── workflow.json
├── pyproject.toml
└── .python-version
```
