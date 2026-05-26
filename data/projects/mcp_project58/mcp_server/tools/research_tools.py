"""Research tools — AI-powered company research with internet search.

Corresponds to n8n nodes:
- Company Research1 (AI Agent + Groq + Tavily Search Internet1)
- Search Internet1 (Tavily tool, mock → simulated results)
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from .utils.log_decorator import log_mcp_call

load_dotenv()

RESEARCH_PROMPT = """You are an expert business analyst. Your task is to research the company: {company_name}.

Your output must be a comprehensive description that identifies the company's name, its core business, and potential opportunities for improving efficiency and effectiveness by implementing AI solutions.

Use the search results provided below to inform your analysis.

Strictly base your analysis on the data provided. Do not hallucinate or invent information.

Your final output must be only the text description. Do not include any introductory sentences or greetings.

Search Results:
{search_results}"""


@log_mcp_call("tool", "search_internet")
def search_internet(query: str) -> str:
    """Search the internet for information (mock Tavily search).

    Returns simulated search results based on the query keywords.

    Args:
        query: Search query string.

    Returns:
        Simulated search result text.
    """
    query_lower = query.lower()

    # Mock search results based on common company/industry keywords
    mock_results = {
        "bank bca": (
            "Bank Central Asia (BCA) is one of Indonesia's largest private banks, "
            "founded in 1957. BCA focuses on transaction banking and digital services. "
            "In 2024, BCA reported total assets of over IDR 1,300 trillion. "
            "The bank has been investing heavily in digital transformation, "
            "including AI-powered fraud detection and chatbot services. "
            "BCA's mobile banking app (myBCA) serves over 30 million users. "
            "Key challenges include legacy system modernization and regulatory compliance."
        ),
        "telkom": (
            "Telkom Indonesia (PT Telekomunikasi Indonesia) is the largest "
            "telecommunications company in Indonesia, a state-owned enterprise. "
            "Telkom provides fixed-line, mobile, data, and internet services. "
            "In 2024, Telkom Group reported revenue of IDR 149 trillion. "
            "The company is expanding into digital business through its subsidiary "
            "Telkomsel and cloud services via TelkomCloud. "
            "Telkom faces challenges in network modernization, 5G rollout, "
            "and competing with digital-native players."
        ),
        "mandiri": (
            "Bank Mandiri is the largest bank in Indonesia by assets, "
            "formed in 1998 as part of the government's bank restructuring program. "
            "Bank Mandiri focuses on corporate, commercial, and retail banking. "
            "In 2024, total assets exceeded IDR 2,000 trillion. "
            "The bank has been a leader in ESG reporting among Indonesian banks, "
            "with a focus on sustainable finance. "
            "Key challenges include ESG compliance, green bond issuance tracking, "
            "and AI-driven risk management."
        ),
    }

    # Find matching mock result
    for key, result in mock_results.items():
        if key in query_lower:
            return result

    return (
        f"Search results for '{query}': The company operates in a competitive market "
        f"with opportunities for AI-driven process automation, data analytics, "
        f"and digital transformation. Industry trends show increasing adoption of "
        f"AI and machine learning across Southeast Asian enterprises."
    )


@log_mcp_call("tool", "research_company")
def research_company(company_name: str, search_results: str) -> str:
    """Research a company using AI (mock Company Research1 Agent).

    Uses OpenAI to analyze search results and produce a comprehensive
    company research description with AI opportunity analysis.

    Args:
        company_name: Name of the company to research.
        search_results: Text from internet search about the company.

    Returns:
        Research description string.
    """
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.1")

    prompt = RESEARCH_PROMPT.format(
        company_name=company_name,
        search_results=search_results,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1024,
    )

    return response.choices[0].message.content.strip()
