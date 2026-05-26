"""MCP Server for English Vocabulary Lookup via Telegram."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastmcp import FastMCP

from mcp_server.tools.utils.log_decorator import setup_logging
from mcp_server.tools.telegram_tools import (
    check_authorization,
    detect_input_type,
    load_config,
    receive_telegram_message,
    reject_unauthorized_user,
    send_telegram_reply,
    set_photo_text,
    set_text_input,
    set_voice_text,
)
from mcp_server.tools.media_tools import (
    download_audio,
    download_image,
    get_photo_file,
    get_voice_file,
)
from mcp_server.tools.ai_tools import analyze_image, dictionary_agent, transcribe_audio
from mcp_server.tools.notion_tools import save_vocabulary_to_notion

logger = setup_logging("logs/server.log")
logger.info("Starting VocabularyBot MCP server...")

mcp = FastMCP("VocabularyBot")

# Step 1 — Telegram Trigger
mcp.tool()(receive_telegram_message)
# Step 2 — Config
mcp.tool()(load_config)
# Step 3 — Authorize User
mcp.tool()(check_authorization)
# Step 4 — Reject Unauthorized
mcp.tool()(reject_unauthorized_user)
# Step 5 — Detect Input Type
mcp.tool()(detect_input_type)
# Step 6 — Text path
mcp.tool()(set_text_input)
# Steps 7-8 — Voice file retrieval
mcp.tool()(get_voice_file)
mcp.tool()(download_audio)
# Step 9 — Whisper transcription
mcp.tool()(transcribe_audio)
# Step 10 — Normalise voice
mcp.tool()(set_voice_text)
# Steps 11-12 — Photo file retrieval
mcp.tool()(get_photo_file)
mcp.tool()(download_image)
# Step 13 — GPT vision OCR
mcp.tool()(analyze_image)
# Step 14 — Normalise photo
mcp.tool()(set_photo_text)
# Step 15 — Dictionary Agent
mcp.tool()(dictionary_agent)
# Step 16 — Telegram reply
mcp.tool()(send_telegram_reply)
# Step 17 — Notion save
mcp.tool()(save_vocabulary_to_notion)

if __name__ == "__main__":
    mcp.run("stdio")
