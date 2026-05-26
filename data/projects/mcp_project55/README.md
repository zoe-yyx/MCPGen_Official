# MCP Project 55 - Automated QR Ticket Scanner & Validator

Converted from n8n workflow. Validates QR code ticket scans against a ticket database and records results.

## Topology

```
Trigger -> Select Latest -> Set Ticket Code -> Read Ticket Rows -> Validate
  ├── VALID       -> Append (STATUS=VALID, with participant info)
  └── TIDAK VALID -> Read Form Responses -> Select Latest -> Append (STATUS=TIDAK VALID)
```

## Tools

| Tool | Description | n8n Source |
|------|-------------|------------|
| `get_form_responses` | Read form responses (mock Google Sheets) | Sheets Update Trigger / Read Form Responses Sheet |
| `select_latest_item` | Get last row from a list | Select Latest Item / Select Latest Form Response |
| `set_ticket_code` | Extract QR code as ticket code | Set Ticket Code Field |
| `read_ticket_rows` | Lookup ticket by code in database | Read Trigger Sheet Rows |
| `validate_ticket` | Check VALID vs TIDAK VALID | Route by Conditional Rules |
| `append_scan_result` | Append result to scan results | Append Scan Results / Append to Scan Results Sheet |

## Setup

```bash
cd mcp_project55
uv sync
```

## Run

```bash
uv run python run_workflow.py
```

## Test

```bash
uv run pytest tests/test_tools.py -v
```
