"""AI analysis tool: generate market summary using OpenAI GPT."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()


SYSTEM_PROMPT = (
    "You are a professional market analysis assistant.\n"
    "Your task is to convert structured trading signals into short, clear, "
    "and professional summaries for managers.\n"
    "Be concise, neutral, and factual.\n"
    "Do NOT give financial advice.\n"
    "Do NOT exaggerate.\n"
    "Focus on signal interpretation and recommended monitoring action."
)


@log_mcp_call("tool", "generate_ai_summary")
def generate_ai_summary(signal_data: str) -> str:
    """Generate a Slack-ready market update using GPT from structured signal data.

    Args:
        signal_data: JSON string with fields: symbol, price, rsi, momentum,
                     volume, avgVolume, volumeSignal, action.

    Returns:
        JSON string with original data plus 'output' field containing the AI summary.
    """
    data = json.loads(signal_data)

    user_prompt = (
        "Create a Slack-ready market update using the signal data below.\n\n"
        "Use:\n"
        "- A short title\n"
        "- Bullet points (•)\n"
        "- A bold Action line\n"
        "- No markdown headers (###)\n\n"
        f"Data:\n"
        f"Symbol: {data.get('symbol')}\n"
        f"Price: {data.get('price')}\n"
        f"RSI: {data.get('rsi')}\n"
        f"Momentum: {data.get('momentum')}\n"
        f"Volume: {data.get('volume')}\n"
        f"Average Volume: {data.get('avgVolume')}\n"
        f"Volume Signal: {data.get('volumeSignal')}\n"
        f"Action: {data.get('action')}\n"
    )

    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER")
    model = os.getenv("MODEL", "gpt-5.1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=500,
        temperature=0.7,
    )

    summary = response.choices[0].message.content or ""
    data["output"] = summary
    return json.dumps(data)
