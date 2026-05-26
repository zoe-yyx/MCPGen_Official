"""AI analysis tools — market insights generation and output parsing."""

from __future__ import annotations

import json
import os
import re

from openai import OpenAI

from .utils.log_decorator import log_mcp_call

SYSTEM_PROMPT = """You are a professional multi-asset financial market strategist and macro analyst.

Your task is to analyze normalized market data across equities, forex and commodities and generate a concise institutional-grade daily market snapshot.

STRICT RULES:
- Output plain text only
- No markdown
- No JSON
- No emojis
- No bold text
- No bullet symbols except hyphen (-) under Key Movers
- Use the EXACT section headings below
- Keep each section concise and professional
- Mention actual percentage changes from provided data
- Focus on trend, sentiment and actionable market insight
- Avoid generic filler statements

MANDATORY OUTPUT FORMAT:

Market Summary:
2-3 lines summarizing the overall market direction and major trends.

Key Movers:
- Always include SPY
- Always include XAU/USD
- Always include USO
- Add 2 to 3 other biggest movers

Risk Sentiment:
State one of:
Risk-on
Risk-off
Mixed

Actionable Insight:
1-2 lines about what traders/investors should watch next.

Outlook:
1-2 lines on expected next-session bias."""


@log_mcp_call("tool")
def generate_market_insights(market_data_json: str) -> str:
    """Use AI to generate a professional daily market report.

    Args:
        market_data_json: JSON string of normalized market data.

    Returns:
        Raw AI-generated text report.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    client = OpenAI(api_key=api_key, base_url=base_url)

    user_prompt = (
        f"Here is today's normalized multi-asset market data:\n\n"
        f"{market_data_json}\n\n"
        f"Analyze the data and generate a professional daily market report.\n\n"
        f"Important:\n"
        f"Follow the exact output format specified in the system instructions.\n"
        f"Use the provided percentage moves and trend data to determine sentiment and outlook."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1024,
    )

    return response.choices[0].message.content or ""


@log_mcp_call("tool")
def parse_ai_output(ai_text: str) -> str:
    """Parse AI-generated market report into structured sections.

    Extracts: market_summary, key_movers, risk_sentiment, insight, outlook.

    Args:
        ai_text: Raw text from the AI model.

    Returns:
        JSON with structured report fields.
    """
    text = ai_text.replace("\\n", "\n").strip()

    def _extract(pattern: str) -> str:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    summary = _extract(r"Market Summary\s*:\s*([\s\S]*?)(?=Key Movers\s*:|$)")
    movers_raw = _extract(r"Key Movers\s*:\s*([\s\S]*?)(?=Risk Sentiment\s*:|Actionable Insight\s*:|$)")
    sentiment = _extract(r"Risk Sentiment\s*:\s*([\s\S]*?)(?=Actionable Insight\s*:|$)")
    insight = _extract(r"Actionable Insight\s*:\s*([\s\S]*?)(?=Outlook\s*:|$)")
    outlook = _extract(r"Outlook\s*:\s*([\s\S]*)")

    # Clean text: remove markdown bold, collapse whitespace
    def _clean(t: str) -> str:
        return re.sub(r"\s+", " ", t.replace("**", "")).strip()

    # Trim to max 2 sentences (safe for decimals like 1.46%)
    def _trim_sentences(t: str, n: int = 2) -> str:
        if not t:
            return ""
        sentences = re.findall(r"(?:[^.!?]|\d\.\d)+[.!?]+", t) or [t]
        return " ".join(sentences[:n]).strip()

    summary = _trim_sentences(_clean(summary))
    sentiment = _clean(sentiment)
    insight = _trim_sentences(_clean(insight))
    outlook = _trim_sentences(_clean(outlook))

    # Parse movers list
    movers = [
        re.sub(r"^[-*•]\s*", "", re.sub(r"\s+", " ", line)).strip()
        for line in movers_raw.split("\n")
        if line.strip()
    ]

    return json.dumps({
        "market_summary": summary,
        "key_movers": movers,
        "risk_sentiment": sentiment,
        "insight": insight,
        "outlook": outlook,
    }, ensure_ascii=False)
