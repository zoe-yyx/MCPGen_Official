"""Tool for the DocAgent LLM conversation loop."""

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()

_client: OpenAI | None = None
_conversation_history: list[dict[str, str]] = []


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("API_KEY", ""),
            base_url=os.getenv("BASE_URL", "ENDPOINT_PLACEHOLDER"),
        )
    return _client


MODEL = os.getenv("MODEL", "gpt-4.1")

SYSTEM_PROMPT = """You are "Legal-Doc Agent", an expert that drafts professional documents from fixed templates.

Your job is to:
1. Help the user select a template from the available catalog.
2. Collect all required placeholder values from the user.
3. For each conditional block, ask if the user wants to include it.
4. Confirm all data with the user before proceeding.
5. Return a structured JSON with all the user's answers.

Be concise, formal, and never guess data — always ask the user.

When you have collected all data, return a JSON object with:
{
  "ready": true,
  "template_id": "<id>",
  "template_name": "<name>",
  "answers": {
    "<PLACEHOLDER>": "<value>",
    ...
    "blocks": {
      "<FLAG>": {"include": true/false, "<INNER_PH>": "<value>"},
      ...
    }
  }
}
"""


@log_mcp_call("tool", "chat_with_doc_agent")
def chat_with_doc_agent(
    user_message: str,
    template_catalog: list[dict[str, Any]],
    template_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a message to the DocAgent and get a response.

    Args:
        user_message: The user's chat input.
        template_catalog: List of available templates.
        template_metadata: Metadata for the selected template (if already selected).

    Returns:
        dict with 'response' (agent text), and optionally 'ready' (bool) + 'data'.
    """
    global _conversation_history

    catalog_str = json.dumps(template_catalog, ensure_ascii=False, indent=2)
    meta_str = json.dumps(template_metadata, ensure_ascii=False, indent=2) if template_metadata else "Not yet loaded."

    system = SYSTEM_PROMPT + f"\n\nAvailable templates:\n{catalog_str}\n\nSelected template metadata:\n{meta_str}"

    _conversation_history.append({"role": "user", "content": user_message})

    messages = [{"role": "system", "content": system}] + _conversation_history

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.3,
    )
    agent_reply = resp.choices[0].message.content or ""
    _conversation_history.append({"role": "assistant", "content": agent_reply})

    # Check if agent is returning structured data
    result: dict[str, Any] = {"response": agent_reply, "ready": False}
    try:
        if '"ready": true' in agent_reply or '"ready":true' in agent_reply:
            import re
            match = re.search(r'\{[\s\S]*\}', agent_reply)
            if match:
                parsed = json.loads(match.group())
                if parsed.get("ready"):
                    result["ready"] = True
                    result["data"] = parsed
    except (json.JSONDecodeError, AttributeError):
        pass

    return result


@log_mcp_call("tool", "reset_conversation")
def reset_conversation() -> str:
    """Reset the DocAgent conversation history.

    Returns:
        Confirmation message.
    """
    global _conversation_history
    _conversation_history = []
    return "Conversation history cleared."
