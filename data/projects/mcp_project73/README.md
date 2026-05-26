# English Vocabulary Lookup via Telegram and Notion

MCP project converted from n8n workflow. A Telegram bot that accepts text, voice, or photo messages from an authorized user, looks up English vocabulary using a GPT dictionary agent with spell-checking, replies via Telegram with a structured vocabulary card, and saves the entry to Notion.

## Workflow Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | Telegram Trigger | Receive message (text / voice / photo) |
| 2 | Config — Edit Me | Load TELEGRAM_CHAT_ID, TARGET_LANGUAGE, etc. |
| 3 | Authorize User | Check sender chat ID; branch to step 4 or 5 |
| 4 | Reject Unauthorized | Send rejection notice; end workflow |
| 5 | Detect Input Type | Route: text→6, voice→7, photo→11 |
| 6 | Set Text Input | Extract text as `chat_input` |
| 7 | Get Voice File | Resolve voice file_id to file_path |
| 8 | Download Audio | Download voice file |
| 9 | Transcribe Audio (Whisper) | OpenAI Whisper speech-to-text |
| 10 | Set Voice Text | Wrap transcription as `chat_input` |
| 11 | Get Photo File | Resolve photo file_id to file_path |
| 12 | Download Image | Download photo |
| 13 | Analyze Image | GPT vision OCR — extract English words |
| 14 | Set Photo Text | Wrap OCR result as `chat_input` |
| 15 | Dictionary Agent | GPT spell-check + structured vocabulary lookup |
| 16 | Send Telegram Reply | Reply with vocabulary card |
| 17 | Save Vocabulary to Notion | Persist entry to Notion database |

## Dictionary Output Format

The GPT agent (Step 15) returns a structured vocabulary card:

```
📖 phenomenon

Part of speech: noun
Definition: something remarkable or unusual that can be perceived
Translation: （尤指不尋常的）現象

Example: Gravity is a natural phenomenon.
重力是一種自然現象。
```

## Notes

- **Telegram**, **Notion** are **mocked** (no credentials needed)
- **OpenAI GPT** is a **real call** using gpt-5.1 for the dictionary agent and image analysis
- Voice transcription is **mocked by default** (`MOCK_AUDIO_TRANSCRIPTION=true`)
- Telegram replies saved to `results/outputs/telegram_reply_*.json`
- Vocabulary entries persisted to `results/outputs/vocabulary.json` and `vocabulary.csv`
- Set `TARGET_LANGUAGE` to any language (Traditional Chinese, Japanese, Spanish, etc.)

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
mcp_project73/
├── mcp_server/
│   ├── server.py                  # MCP Server (17 tools)
│   └── tools/
│       ├── telegram_tools.py      # Telegram mock (Steps 1-6, 10, 14, 16)
│       ├── media_tools.py         # Voice/photo file retrieval mock (Steps 7-8, 11-12)
│       ├── ai_tools.py            # Whisper, GPT vision, dictionary agent (Steps 9, 13, 15)
│       ├── notion_tools.py        # Notion mock (Step 17)
│       └── utils/log_decorator.py
├── tests/test_tools.py            # 22 tests
├── run_workflow.py                # Steps 1-17, 5 demo sessions
├── workflow.json
└── logs/ results/
```
