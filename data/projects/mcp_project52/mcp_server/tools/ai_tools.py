"""
AI tools – mirrors the LangChain / LLM nodes in the n8n workflow:

  • tool_classify_relevance  → "Relevance Classification for Topic Monitoring"
                               (@n8n/n8n-nodes-langchain.textClassifier)
  • tool_summarize_article   → "Basic LLM Chain"
                               (@n8n/n8n-nodes-langchain.chainLlm)

Both tools call an OpenAI-compatible API (default: gpt-5.1).
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from openai import OpenAI

from mcp_server.tools.utils.logging_decorator import log_tool_call, setup_logging

logger = setup_logging("logs/server.log", console_output=False)

# ── OpenAI-compatible client factory ──────────────────────────────────────────

def _get_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER"),
    )


_CLASSIFICATION_MODEL = os.getenv("OPENAI_CLASSIFICATION_MODEL", "gpt-5.1")
_SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-5.1")

# ── Classification ─────────────────────────────────────────────────────────────

_RELEVANT_DESCRIPTION = (
    "Articles related to AI Agent, LLM Agent, autonomous agents, "
    "multi-agent systems, agent frameworks (e.g. LangChain, CrewAI, AutoGen, MCP), "
    "agentic workflows, tool-use, function calling, RAG with agents, "
    "or real-world Agent application cases."
)
_NOT_RELEVANT_DESCRIPTION = (
    "Articles not related to AI Agent topics — e.g. pure product ads, "
    "recruitment notices, entertainment, lifestyle, or general news "
    "without any Agent/LLM/autonomous-system content."
)

_CLASSIFICATION_SYSTEM = """\
You are a content classifier. Given an article's title and content snippet, decide whether
it is "relevant" or "not_relevant" according to the criteria below.

relevant     : {relevant_desc}
not_relevant : {not_relevant_desc}

Respond ONLY with a JSON object in this exact format (no markdown, no extra keys):
{{"category": "relevant"}}
or
{{"category": "not_relevant"}}
"""


@log_tool_call(logger)
def tool_classify_relevance(
    title: str,
    cleaned_content: str,
    relevant_description: str = _RELEVANT_DESCRIPTION,
    not_relevant_description: str = _NOT_RELEVANT_DESCRIPTION,
    use_mock: bool = False,
) -> dict[str, Any]:
    """
    Classify whether an article is relevant for topic monitoring.

    Mirrors the n8n "Relevance Classification for Topic Monitoring" textClassifier node.
    Articles classified as "not_relevant" are discarded (fallback: discard).

    Args:
        title:                  Article title.
        cleaned_content:        Cleaned plain-text content.
        relevant_description:   Natural-language description of "relevant" articles.
        not_relevant_description: Natural-language description of "not_relevant".
        use_mock:               If True, always return "relevant" (for testing).

    Returns:
        Dict with keys:
          - category: "relevant" | "not_relevant"
          - kept: bool (True when category is "relevant")
    """
    if use_mock:
        return {"category": "relevant", "kept": True}

    client = _get_client()
    system_prompt = _CLASSIFICATION_SYSTEM.format(
        relevant_desc=relevant_description,
        not_relevant_desc=not_relevant_description,
    )
    user_text = f"{title}\n\n{cleaned_content[:2000]}"

    response = client.chat.completions.create(
        model=_CLASSIFICATION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0,
        max_tokens=50,
    )

    raw = response.choices[0].message.content or ""
    try:
        parsed = json.loads(raw.strip())
        category: str = parsed.get("category", "not_relevant")
    except json.JSONDecodeError:
        logger.warning("Failed to parse classification response: %s", raw)
        category = "not_relevant"

    kept = category == "relevant"
    logger.info("Classification: %s | kept=%s | title=%s", category, kept, title[:60])
    return {"category": category, "kept": kept}


# ── Summarisation ──────────────────────────────────────────────────────────────

_SUMMARY_SYSTEM = """\
You are an expert AI assistant responsible for analyzing and summarizing articles from \
WeChat public accounts **in Chinese**, formatting the output into Slack-compatible messages. \
Your task is to provide a deep, insightful summary that captures the main ideas, key points, \
and purpose of the article, while adding your own thoughtful analysis and interpretation to \
enhance understanding. Follow the guidelines below and use Slack-specific Markdown format.

---

### Instructions:
1. **Input Analysis**: The input text may include incomplete HTML fragments, JavaScript code, \
or metadata. Focus only on meaningful textual content (e.g., article body or description) and \
ignore non-content elements (e.g., scripts, tags, or emojis).
2. **Summary Requirements**:
   - Provide a comprehensive overview of the article's content, highlighting the central theme \
and key points without unnecessary details.
   - Add your own analysis and interpretation to offer deeper insights, connecting the content \
to broader contexts or implications.
   - Use clear, natural, and professional Chinese suitable for a general audience.
3. **Output Structure**:
   - **Title with Link**: Format the article title as a clickable link using Slack Markdown: \
`<URL|*文章标题*>`. Ensure the title is engaging and reflective of the content.
   - **Summary Sections**: Use **bold text** (`*`) for section headings \
(e.g., *文章概要*, *关键要点*, *背景与相关性*) to guide readers.
   - **Key Points**: Present key insights as bullet points using `•` for concise and \
scannable information.
   - **Context and Relevance**: Explain the article's importance, its relevance to readers' \
interests, and its connection to trends or industry developments.
4. **Slack Markdown Formatting**:
   - **Bold text**: `*bold text*`.
   - **Italic text**: `_italic text_` (optional for emphasis).
   - **Bullet points**: Use `•` for lists.
   - **Dividers**: Use `---` to separate sections.
5. **Length**: Keep the summary concise yet comprehensive, ideally within 300–500 Chinese \
characters per section, and no more than 3 sections.
6. **Language**: Respond entirely in Chinese (Simplified).
"""


@log_tool_call(logger)
def tool_summarize_article(
    cleaned_content: str,
    article_url: str = "",
    title: str = "",
    use_mock: bool = False,
) -> dict[str, Any]:
    """
    Generate a Slack-formatted Chinese summary of an article.

    Mirrors the n8n "Basic LLM Chain" node with the OpenAI Chat Model (gpt-4.1-nano).

    Args:
        cleaned_content: Plain-text article content (output of tool_clean_html_content).
        article_url:     Original article URL (used for the Slack link).
        title:           Article title (used for the Slack link).
        use_mock:        If True, return a placeholder summary (for testing).

    Returns:
        Dict with key:
          - text: Slack-formatted Chinese summary string.
    """
    if use_mock:
        mock_summary = (
            f"<{article_url}|*{title}*>\n\n"
            "*文章概要*\n• 这是一篇测试摘要，用于验证工作流。\n\n"
            "*关键要点*\n• Mock 模式下生成。\n\n"
            "*背景与相关性*\n• 无实际内容。"
        )
        return {"text": mock_summary}

    client = _get_client()
    user_content = (
        f"Article URL: {article_url}\nTitle: {title}\n\n{cleaned_content[:6000]}"
    )

    response = client.chat.completions.create(
        model=_SUMMARY_MODEL,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    text = response.choices[0].message.content or ""
    logger.info("Summarized article (len=%d): %s…", len(text), title[:60])
    return {"text": text}