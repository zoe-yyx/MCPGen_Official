# Instant Ad Banner Generator

MCP project converted from n8n workflow. Generates professional marketing banners from a Japanese product description received via LINE: GPT optimizes the prompt, submits to AI image generation (Nano Banana Pro / kie.ai), polls for completion, uploads the banner to S3, and delivers it back via LINE reply.

## Workflow Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | LINE Webhook | Receive Japanese product/campaign text from LINE user |
| 2 | Extract Line Data | Parse replyToken, userId, message from webhook |
| 3 | Optimize Prompt | GPT writes a detailed English image generation prompt |
| 4 | Extract Prompt Text | Clean the prompt text from GPT response |
| 5 | Submit Image Generation | Submit job to mock kie.ai Nano Banana Pro API |
| 6 | Wait for Processing | 10-second wait (mock, instant) |
| 7 | Check Job Status | Poll mock kie.ai status endpoint |
| 8 | Wait for Generation | 10-second wait (mock, instant) |
| 9 | Parse Result | Extract imageUrl; loop back to Step 7 if still processing |
| 10 | Download Image | Download image; falls back to placeholder PNG if unreachable |
| 11 | Upload to S3 | Mock S3 upload → local file + fake public URL |
| 12 | Send LINE Reply | Mock LINE image reply saved to results/outputs/ |

## Notes

- **LINE**, **kie.ai (Nano Banana Pro)**, and **AWS S3** operations are **mocked** (no credentials needed)
- **OpenAI GPT** is a **real call** using GPT-5.1 for Japanese marketing prompt optimization (Step 3)
- Generated banner PNGs saved to `results/outputs/banner_*.png`
- S3 upload metadata saved to `results/outputs/banner_*_meta.json`
- LINE reply payloads saved to `results/outputs/line_reply_*.json`
- Poll loop: up to 5 attempts before raising an error (mock always succeeds on first try)

## Setup

```bash
cp .env.template .env
# Edit .env with your OpenAI API key
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
mcp_project71/
├── mcp_server/
│   ├── server.py                  # MCP Server (12 tools)
│   └── tools/
│       ├── line_tools.py          # LINE mock (Steps 1, 2, 12)
│       ├── ai_tools.py            # GPT prompt optimization (Steps 3, 4)
│       ├── image_gen_tools.py     # kie.ai mock (Steps 5-9)
│       ├── storage_tools.py       # Download + S3 mock (Steps 10, 11)
│       └── utils/log_decorator.py
├── tests/test_tools.py            # 18 tests
├── run_workflow.py                # Steps 1-12 with poll loop
├── workflow.json
└── logs/ results/
```
