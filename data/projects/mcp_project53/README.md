# 🗂️ HR Contract Archiving — MCP Project

Converted from the n8n workflow **"Legal & Compliance Document Archiving"**.

## What it does

Automates the full HR contract intake chain:

1. **Validate & Enrich** — normalise employee name, generate a structured filename (`EMP-ID_LASTNAME_CONTRACTTYPE_DATE.ext`), build the folder path.
2. **Duplicate Check** — search local records; halt immediately if a contract is already on file (mirrors n8n's 409 Conflict branch).
3. **CDN Upload** — stage the file locally (replace with S3/Azure Blob/UploadToURL in production).
4. **Folder Resolution** — find or create the local folder mirroring `HR/Contracts/{Year}/{Dept}/{Employee}/`.
5. **Document Upload** — copy the file into the resolved folder with the canonical name.
6. **Record Lookup** — check whether the employee already has a DB entry.
7. **Record Upsert** — create or update the contract record (local JSON, replaces Airtable).
8. **Confirmation Email** — send HTML email to HR (+ employee if `notifyEmployee=true`); falls back to writing HTML to `logs/emails/` if SMTP is unconfigured.
9. **Final Response** — assemble the complete audit summary and persist it to `results/outputs/`.

## Quick start

```bash
# 1. Install dependencies
uv sync

# 2. Copy and configure environment
cp .env.template .env
# Edit .env — only SMTP fields are needed; everything else works without them.

# 3. Run the workflow (uses demo payload + stub PDF)
uv run python run_workflow.py

# 4. Run tests
uv run pytest -v
```

## Project structure

```
hr_contract_archive/
├── mcp_server/
│   ├── server.py                  # FastMCP server, registers all tools
│   └── tools/
│       ├── validation_tools.py    # tool_validate_and_enrich
│       ├── storage_tools.py       # tool_check_duplicate, tool_find_or_create_folder,
│       │                          # tool_upload_document, tool_find_employee_record,
│       │                          # tool_upsert_employee_record
│       ├── notification_tools.py  # tool_upload_to_cdn, tool_send_confirmation_email,
│       │                          # tool_build_final_response
│       └── utils/
│           └── logging_decorator.py
├── tests/
│   └── test_tools.py
├── logs/
│   ├── server.log
│   ├── workflow.log
│   └── emails/                    # HTML email fallback
├── results/
│   ├── outputs/
│   │   ├── airtable.json          # local contract records DB
│   │   ├── contracts/             # stored documents (mirrors Drive)
│   │   ├── cdn_staging/           # CDN-staged copies
│   │   └── archive_result_*.json  # per-run audit summaries
│   └── metrics/
├── run_workflow.py
├── workflow.json
├── pyproject.toml
└── .env.template
```

## n8n → MCP node mapping

| n8n Node | MCP Tool | Notes |
|---|---|---|
| Webhook - Receive Contract | `run_workflow.py` `DEMO_PAYLOAD` | Entry point |
| Validate & Enrich Payload | `tool_validate_and_enrich` | Pure Python port |
| Airtable - Duplicate Check | `tool_check_duplicate` | Local JSON DB |
| IF Duplicate Exists? / Respond 409 | Handled in `run_workflow.py` | Early return |
| Has Remote URL? | Handled in `tool_upload_to_cdn` | Both paths merged |
| Upload to URL (Remote/Binary) | `tool_upload_to_cdn` | Local staging |
| Extract CDN URL | Inline in `tool_upload_to_cdn` | Returns cdnUrl |
| Drive - Find Employee Folder | `tool_find_or_create_folder` | Local filesystem |
| Drive - Create Employee Folder | `tool_find_or_create_folder` | Merged |
| Merge Folder ID | `tool_find_or_create_folder` | Merged |
| Drive - Upload Document | `tool_upload_document` | Local copy |
| Airtable - Find Employee Record | `tool_find_employee_record` | Local JSON DB |
| Prepare Airtable Update | Inline in `run_workflow.py` | Thin glue |
| Airtable - Update/Create Record | `tool_upsert_employee_record` | Merged |
| Merge Airtable Result | Inline in `run_workflow.py` | |
| Send Confirmation Email | `tool_send_confirmation_email` | SMTP + file fallback |
| Build Final Response | `tool_build_final_response` | Mirrors 201 response |
| Respond to Webhook | Return value of `run_workflow.py` | |

## Replacing local storage with real APIs

- **CDN upload**: Replace the `tool_upload_to_cdn` body with your UploadToURL / S3 / Cloudflare R2 call.
- **Google Drive**: Replace `tool_find_or_create_folder` and `tool_upload_document` with `google-api-python-client` calls.
- **Airtable**: Replace `_load_db` / `_save_db` in `storage_tools.py` with `pyairtable` calls; swap `airtable.json` for real base/table IDs.
- **Gmail**: The SMTP path in `tool_send_confirmation_email` already works for Gmail with an App Password; for OAuth2 use `google-auth-oauthlib`.