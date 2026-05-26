"""Email tools — AI-powered sales email drafting.

Corresponds to n8n nodes:
- AI Sales Assistant (AI Agent + Groq + Tavily Search Internet2 + Structured Output Parser)
- Search Internet2 (Tavily tool, reuses search_internet from research_tools)
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from .utils.log_decorator import log_mcp_call

load_dotenv()

EMAIL_DRAFT_PROMPT = """You are an expert AI Sales Assistant, tasked with drafting a personalized and relevant email based on the provided data and additional research.

1. PRIMARY CONTEXT:
Sender's Company: Ainabler.com (IT consulting firm specializing in AI & Automation).
Sender's Name: Hanif R (Technical Sales).
Target Company: {company}
Target Recipient: {recipient_name}
Recipient's Position: {recipient_position}
Sales Stage: {stage}
Main Email Theme: {theme}
Key Information: {research_result}
Sample Message (For inspiration, not a rigid template): {sample_message}

2. ADDITIONAL INDUSTRY CONTEXT:
{additional_research}

3. SERVICES OFFERED:
{services}

4. TASK:
Use ALL the information above to create one email draft.
- Personalization: Mention the recipient's company name and position.
- Relevance: Connect industry challenges with Ainabler.com solutions.
- Value Proposition: Craft a natural offer based on services and target's business.
- Call to Action: Propose a brief discussion to explore possibilities.

5. OUTPUT FORMAT (MANDATORY):
Your final response MUST be a single, valid JSON object. Do not include any text outside this JSON.

{{
  "emailSubject": "A compelling and specific email subject",
  "emailBody": "The complete, personalized, and relevant email body."
}}"""


@log_mcp_call("tool", "draft_sales_email")
def draft_sales_email(
    company: str,
    recipient_name: str,
    recipient_position: str,
    research_result: str,
    stage: str,
    theme: str,
    sample_message: str,
    services_json: str,
    additional_research: str,
) -> dict[str, str]:
    """Draft a personalized sales email using AI (mock AI Sales Assistant).

    Args:
        company: Target company name.
        recipient_name: Recipient's name.
        recipient_position: Recipient's job title.
        research_result: Company research text.
        stage: Sales stage (e.g., 'Leads').
        theme: Email theme from template.
        sample_message: Sample message from template.
        services_json: JSON string of services list.
        additional_research: Additional search results for a data-driven hook.

    Returns:
        Dict with 'emailSubject' and 'emailBody'.
    """
    services = json.loads(services_json) if isinstance(services_json, str) else services_json
    services_text = "\n".join(
        f"- {s['Product']}: {s['Description']}" for s in services
    )

    prompt = EMAIL_DRAFT_PROMPT.format(
        company=company,
        recipient_name=recipient_name,
        recipient_position=recipient_position,
        stage=stage,
        theme=theme,
        research_result=research_result,
        sample_message=sample_message,
        services=services_text,
        additional_research=additional_research,
    )

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.1")

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    return json.loads(raw)
