# AI Image to Professional Video Workflow — MCP Project

Converts the n8n workflow **"AI Image to Professional Video Workflow using NanoBanana Ultra & Kling AI"** into a fully self-contained MCP (Model Context Protocol) project backed by FastMCP.

## What it does

| Step | n8n Node | MCP Tool | Notes |
|------|----------|----------|-------|
| 1 | Get url image (Google Sheets) | `get_image_records` | Google Sheets → local CSV |
| 2 | Download image (Google Drive) | `download_source_image` | Google Drive → local folder |
| 3 | Build Public Image URL nano (tmpfiles) | `upload_image_public` | tmpfiles → local copy + mock URL |
| 4 | Edit Fields: contactSheetPrompt | `build_contact_sheet_prompt` | Hardcoded fashion prompt |
| 5 | NanoBanana ULTRA: Contact Sheet | `generate_contact_sheet` | AtlasCloud API → local image transforms |
| 6 | download image nano (poll) | `poll_generation_result` | Poll prediction → instant mock |
| 7 | Upload file to google drive | `save_to_drive` | Google Drive → local output |
| 8 | Update with new image (Sheets) | `update_record` | Google Sheets → CSV update |
| 9 | Get row(s) in sheet | `get_image_records` | Read contact_done records |
| 10 | Edit Image (info) | `get_image_info` | Get dimensions via Pillow |
| 11 | Crop (TL/TC/TR/BL) | `crop_image` | Crop contact sheet into 4 frames |
| 12 | Upload crops (tmpfiles) | `upload_image_public` | Upload 4 frames |
| 13 | Kling Generation (×3) | `generate_video_clip` | Kling API → mock video manifest |
| 14 | download video kling (×3) | `poll_video_result` | Poll video → instant mock |
| 15 | Merge 3 Videos (FFmpeg) | `merge_videos` | fal.ai FFmpeg → mock merge |
| 16 | Update row in sheet | `update_record` | Status → video_done |
| 17 | Upload media (Blotato) | `upload_media` | Blotato → local JSONL log |
| 18 | Create post (YouTube) | `create_social_post` | Blotato YouTube → local JSONL log |

**Mock mode (default):** the entire workflow runs without any API keys.
All external services (AtlasCloud, tmpfiles, Google Drive/Sheets, Blotato) are simulated locally.

---

## Project structure

```
mcp_project59/
├── README.md
├── .env                           # environment config (all mocked)
├── pyproject.toml                 # uv-managed dependencies
├── workflow.json                  # workflow step configuration
├── run_workflow.py                # main workflow runner (fastmcp Client)
│
├── data/
│   ├── images.csv                 # image records (auto-created)
│   └── source_images/             # source images (auto-created with sample)
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                  # FastMCP server, registers 15 tools
│   └── tools/
│       ├── __init__.py
│       ├── image_tools.py         # CSV records, image I/O, cropping
│       ├── generation_tools.py    # Mock NanoBanana, Kling, FFmpeg
│       ├── publishing_tools.py    # Mock Blotato upload + YouTube post
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
    ├── outputs/                   # contact sheets, crops, video manifests
    └── metrics/                   # run_metrics.json
```

---

## Quick start

```bash
# Install dependencies
uv sync

# Run the full workflow
uv run python run_workflow.py

# Run tests (no MCP server needed)
uv run pytest tests/ -v
```

---

## How it works

### Phase 1 — Contact Sheet Generation
1. Reads a record from CSV where `status = nanobanana_done`
2. Downloads the source image from local storage (mock Google Drive)
3. Uploads the image to get a public URL (mock tmpfiles)
4. Builds the fashion-photography contact-sheet prompt
5. Generates a 2×3 contact sheet with 6 camera-angle variants (mock NanoBanana ULTRA — uses Pillow transforms)
6. Polls the prediction result (instant in mock mode)
7. Saves the contact sheet to local output (mock Google Drive)
8. Updates the CSV record: `status → contact_done`

### Phase 2 — Video Creation & Publishing
9. Reads records where `status = contact_done`
10. Gets contact-sheet dimensions
11. Crops the contact sheet into 4 individual frames
12. Uploads the 4 cropped frames
13. Generates 3 video clips using start/end frame pairs (mock Kling AI)
14. Polls the 3 video generation results
15. Merges the 3 clips into one final video (mock FFmpeg)
16. Updates the CSV record: `status → video_done`
17. Uploads the final video to Blotato (mock)
18. Creates a YouTube post (mock)

---

## External services (all mocked)

| Service | Purpose | Mock implementation |
|---------|---------|-------------------|
| Google Sheets | Image record storage | Local CSV file |
| Google Drive | Image upload/download | Local folder |
| tmpfiles.org | Public image URLs | Local copy + fake URL |
| AtlasCloud (NanoBanana ULTRA) | AI image generation | Pillow transforms |
| AtlasCloud (Kling AI) | AI video generation | JSON manifest files |
| fal.ai (FFmpeg) | Video merging | JSON manifest file |
| Blotato | Social media publishing | JSONL log files |

---

## No LLM API required

This workflow uses only image/video generation APIs (NanoBanana ULTRA, Kling AI), not text LLMs. All generation is mocked locally using Pillow for image processing and JSON manifests for video placeholders.
