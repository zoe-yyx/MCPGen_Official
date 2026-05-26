"""Tools for DocProcess subworkflow: verify choice, format data, parse JSON."""

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("API_KEY", ""),
            base_url=os.getenv("BASE_URL", "ENDPOINT_PLACEHOLDER"),
        )
    return _client


MODEL = os.getenv("MODEL", "gpt-4.1")


@log_mcp_call("tool", "verify_user_choice")
def verify_user_choice(
    user_choice_name: str,
    user_choice_id: str,
    template_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify that a template name matches its ID using LLM.

    Args:
        user_choice_name: Template name chosen by user.
        user_choice_id: Template ID provided by agent.
        template_catalog: List of all templates with id and name.

    Returns:
        dict with 'eslesme' (bool match), 'user_choice_name', 'user_choice_id',
        and optionally 'correct_id'.
    """
    catalog_str = json.dumps(template_catalog, ensure_ascii=False)
    prompt = f"""You are verifying whether a document name and ID are correctly matched.

Template catalog:
{catalog_str}

User selected: name="{user_choice_name}", id="{user_choice_id}"

If the name and ID match correctly in the catalog, respond with:
{{"eslesme": true, "user_choice_name": "{user_choice_name}", "user_choice_id": "{user_choice_id}"}}

If they do NOT match, respond with:
{{"eslesme": false, "user_choice_name": "{user_choice_name}", "user_choice_id": "{user_choice_id}", "correct_id": "<the correct id from catalog>"}}

Respond ONLY with valid JSON."""

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    raw = resp.choices[0].message.content or ""
    cleaned = _extract_json(raw)
    return json.loads(cleaned)


@log_mcp_call("tool", "format_user_data")
def format_user_data(
    doc_id: str,
    metadata: dict[str, Any],
    user_answers: dict[str, Any],
) -> dict[str, Any]:
    """Format user answers against template metadata using LLM.

    Args:
        doc_id: The copied document ID.
        metadata: Template metadata (placeholders, conditionals).
        user_answers: Raw user-provided answers.

    Returns:
        dict with 'docId' and 'data' (formatted placeholder values + blocks).
    """
    meta_str = json.dumps(metadata, ensure_ascii=False)
    answers_str = json.dumps(user_answers, ensure_ascii=False)

    prompt = f"""Match the user answers to the correct template placeholders.

Template metadata:
{meta_str}

User answers:
{answers_str}

Return a JSON object in this exact format:
{{
  "docId": "{doc_id}",
  "data": {{
    "<PLACEHOLDER_1>": "<value>",
    "<PLACEHOLDER_2>": "<value>",
    "blocks": {{
      "<FLAG_NAME>": {{
        "include": true_or_false,
        "<INNER_PLACEHOLDER>": "<value if include=true>"
      }}
    }}
  }}
}}

Rules:
- Use EXACT placeholder names from metadata (UPPER_CASE).
- Set include=false for blocks the user declined.
- DO NOT invent placeholder names.
Respond ONLY with valid JSON."""

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    raw = resp.choices[0].message.content or ""
    cleaned = _extract_json(raw)
    return json.loads(cleaned)


@log_mcp_call("tool", "formatting_correction")
def formatting_correction(raw_text: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM output (handles markdown code blocks).

    Args:
        raw_text: Raw LLM output possibly wrapped in ```json ... ```.

    Returns:
        Parsed dict.
    """
    cleaned = _extract_json(raw_text)
    return json.loads(cleaned)


def _extract_json(text: str) -> str:
    """Extract JSON string from text, stripping markdown code fences."""
    match = re.search(r"```json\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()
