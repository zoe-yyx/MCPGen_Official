"""
AI analysis tools — replaces two n8n nodes:

  • "Sentiment Analyzer"  → tool_analyze_sentiment
  • "Summarize Reviews"   → tool_summarize_reviews

Both backed by any OpenAI-compatible API (configured via .env).
mock_mode=True lets the whole workflow run without any API key.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from openai import OpenAI

from mcp_server.tools.utils.logging_decorator import setup_logging, log_tool_call

logger = setup_logging("logs/server.log", console_output=False)

SentimentCategory = Literal["positive", "neutral", "negative"]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SENTIMENT_SYSTEM = """You are a sentiment analysis engine.
Analyse the customer reviews provided and reply with a JSON object ONLY.
No markdown, no explanation — raw JSON only.

Required shape:
{
  "category": "positive" | "neutral" | "negative",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one sentence>"
}

Rules:
- positive  : overall majority of reviews praise the product
- negative  : overall majority of reviews criticise the product
- neutral   : genuinely mixed or inconclusive
"""

_SUMMARIZE_SYSTEM = """You are a concise review summariser.
Write a 3-5 sentence executive summary covering:
  1. Main praise points
  2. Main complaints
  3. Overall recommendation

Return plain text only — no bullet points, no markdown.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _openai_client(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def _mock_sentiment(reviews_text: str) -> dict[str, Any]:
    """Heuristic mock: count negative keywords to decide category."""
    neg_kw = ["broke", "terrible", "disappointed", "bad", "worst", "waste", "poor"]
    pos_kw = ["love", "great", "excellent", "best", "perfect", "recommend", "amazing"]
    neg = sum(reviews_text.lower().count(w) for w in neg_kw)
    pos = sum(reviews_text.lower().count(w) for w in pos_kw)
    if neg > pos:
        cat: SentimentCategory = "negative"
    elif pos > neg:
        cat = "positive"
    else:
        cat = "neutral"
    return {"category": cat, "confidence": 0.80, "reasoning": "Mock heuristic via keyword count."}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@log_tool_call(logger)
async def tool_analyze_sentiment(
    reviews: str,
    base_url: str = "",
    api_key: str = "",
    model_name: str = "gpt-5.1",
    mock_mode: bool = True,
) -> dict[str, Any]:
    """
    Classify overall sentiment of review text as positive / neutral / negative.

    Args:
        reviews:    Formatted review text from tool_format_reviews.
        base_url:   OpenAI-compatible API base URL.
        api_key:    API key.
        model_name: Model name to use.
        mock_mode:  When True, return a heuristic result without API call.

    Returns:
        {
          "sentimentAnalysis": {
            "category":   "positive"|"neutral"|"negative",
            "confidence": float,
            "reasoning":  str
          },
          "reviews": str   # pass-through for downstream tools
        }
    """
    if mock_mode:
        analysis = _mock_sentiment(reviews)
        logger.info(f"[MOCK] sentiment={analysis['category']}")
        return {"sentimentAnalysis": analysis, "reviews": reviews}

    client = _openai_client(base_url, api_key)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": _SENTIMENT_SYSTEM},
            {"role": "user",   "content": f"Reviews:\n{reviews}"},
        ],
        temperature=0.0,
        max_tokens=256,
    )

    raw = response.choices[0].message.content.strip()
    try:
        analysis = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Sentiment JSON parse failed, raw={raw[:200]}")
        analysis = {"category": "neutral", "confidence": 0.5, "reasoning": raw}

    logger.info(f"Sentiment: {analysis.get('category')} conf={analysis.get('confidence')}")
    return {"sentimentAnalysis": analysis, "reviews": reviews}


@log_tool_call(logger)
async def tool_summarize_reviews(
    reviews: str,
    base_url: str = "",
    api_key: str = "",
    model_name: str = "gpt-5.1",
    mock_mode: bool = True,
) -> dict[str, Any]:
    """
    Generate a concise executive summary of customer reviews.

    Args:
        reviews:    Formatted review text from tool_format_reviews.
        base_url:   OpenAI-compatible API base URL.
        api_key:    API key.
        model_name: Model name to use.
        mock_mode:  When True, return a static placeholder summary.

    Returns:
        {
          "output": {
            "text": str   # executive summary paragraph
          }
        }
    """
    if mock_mode:
        summary = (
            "Mock Summary: The product has received mixed reviews. "
            "Customers appreciate its value and fast delivery, but several report "
            "durability issues after short-term use. "
            "Overall sentiment is slightly negative; quality improvements are recommended "
            "before a broader recommendation can be made."
        )
        logger.info("[MOCK] summary generated")
        return {"output": {"text": summary}}

    client = _openai_client(base_url, api_key)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": _SUMMARIZE_SYSTEM},
            {"role": "user",   "content": f"Reviews to summarise:\n{reviews}"},
        ],
        temperature=0.3,
        max_tokens=512,
    )

    text = response.choices[0].message.content.strip()
    logger.info(f"Summary generated ({len(text)} chars)")
    return {"output": {"text": text}}
