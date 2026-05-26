# Threads Video Downloader & Google Drive Logger

MCP project converted from n8n workflow. Accepts a Threads URL via a web form, fetches video metadata from the Threads Downloader RapidAPI, downloads the video file, uploads it to Google Drive with public sharing, and logs the result to Google Sheets. Failed downloads (no video found) are also logged with N/A.

## Workflow Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | On form submission | User submits Threads URL via form |
| 2 | Fetch Threads Video Data | POST URL to RapidAPI to get video metadata |
| 3 | Check If Video Exists | Verify download URL present; found→4, missing→8 |
| 4 | Download Threads Video File | Download video binary from API URL |
| 5 | Upload Video to Google Drive | Upload video to configured Drive folder |
| 6 | Set Google Drive Sharing Permissions | Make file accessible via shareable link |
| 7 | Log Success to Google Sheets | Append URL + Drive link to log |
| 8 | Wait Before Logging Failure | Brief pause before failure log |
| 9 | Log Failed Download to Google Sheets | Append URL + "N/A" to log |

## Notes

- **RapidAPI**, **Google Drive**, and **Google Sheets** are **mocked** (no credentials needed)
- Mock API: valid `threads.net` URLs return a video; other URLs return no video
- Videos saved to `results/outputs/threads_video_*.mp4` (placeholder MP4)
- Drive uploads copied to `results/outputs/mock_drive/`
- Sheets log persisted to `results/outputs/download_log.csv` and `download_log.json`

## Setup

```bash
cp .env.template .env
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
mcp_project74/
├── mcp_server/
│   ├── server.py                  # MCP Server (9 tools)
│   └── tools/
│       ├── form_tools.py          # Form trigger mock (Step 1)
│       ├── threads_tools.py       # RapidAPI mock + video check (Steps 2-3)
│       ├── download_tools.py      # Video download mock (Step 4)
│       ├── drive_tools.py         # Google Drive mock (Steps 5-6)
│       ├── sheets_tools.py        # Google Sheets mock + wait (Steps 7-9)
│       └── utils/log_decorator.py
├── tests/test_tools.py            # 27 tests
├── run_workflow.py                # Steps 1-9, 4 demo URLs
├── workflow.json
└── logs/ results/
```
