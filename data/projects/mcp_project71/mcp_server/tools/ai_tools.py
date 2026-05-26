"""AI prompt optimization tools for mcp_project71 — Japanese marketing banner."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()

_SYSTEM_PROMPT = """\
You are an expert Marketing Creative Director for the Japanese market.
The user will send details for an ad banner in Japanese (Product, Target Audience, Catch Copy).
Your goal is to write a highly detailed English prompt for an AI image generator.

IMPORTANT RULES:
1. Analyze the target audience and suggest appropriate color palette, mood, and design style.
2. Describe the visual composition with clear space for text overlay.
3. Include the specific Japanese Catch Copy text, instructing to render it clearly and legibly.
4. Specify camera angle, lighting, product placement, and overall aesthetic.
5. Keep the prompt focused and under 500 characters for optimal generation.
6. Output ONLY the English prompt text, nothing else — no explanations, no meta-commentary.
7. NEVER use double quotes in your response. Use single quotes or [brackets] for emphasis instead.

Example format:
'Professional product photography, [product description], featuring Japanese text [キャッチコピー] in bold modern font, [composition details], [lighting style], [color palette], negative space for additional text, high quality, 8K resolution'

Remember: Output ONLY the prompt text, nothing before or after. NO DOUBLE QUOTES.\
"""


@log_mcp_call("tool", "optimize_prompt")
def optimize_prompt(message: str) -> str:
    """Use GPT to create a detailed English image generation prompt for a Japanese marketing banner."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER")
    model = os.getenv("MODEL", "gpt-5.1")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        temperature=0.7,
        max_tokens=600,
    )
    prompt_text = (response.choices[0].message.content or "").strip()

    # Return in Gemini-compatible format so extract_prompt_text can parse it generically
    return json.dumps({
        "content": {
            "parts": [{"text": prompt_text}]
        },
        "raw_text": prompt_text,
    })


@log_mcp_call("tool", "extract_prompt_text")
def extract_prompt_text(response_json: str, user_id: str = "") -> str:
    """Parse the GPT/Gemini response and return a clean prompt string."""
    data = json.loads(response_json)

    prompt_text = ""

    # Try Gemini-format first
    try:
        prompt_text = data["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        pass

    # Fallback to raw_text
    if not prompt_text:
        prompt_text = data.get("raw_text", "")

    # Clean up escape artefacts
    prompt_text = (
        prompt_text
        .replace('\\"', '"')
        .strip()
        .strip("[]\"'")
        .strip()
    )

    return json.dumps({
        "prompt": prompt_text,
        "user_id": user_id,
    })
