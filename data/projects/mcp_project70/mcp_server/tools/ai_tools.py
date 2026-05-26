"""AI Solution Architect tool using OpenAI GPT for mcp_project70."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()

SYSTEM_PROMPT = """You are an expert n8n Solution Architect. Analyze the user's automation idea and provide a concrete n8n workflow construction plan.

Output ONLY a valid JSON object with exactly these keys:
{
  "title": "Refined Title of the Idea",
  "nodes": "List of recommended nodes from Trigger to Action. Explain the flow clearly.",
  "challenges": "Potential technical difficulties, API limits, or authentication pitfalls.",
  "improvements": "Ideas to make the workflow more robust (e.g., error handling) or valuable.",
  "alternatives": "Alternative approaches using lateral thinking.",
  "slack_message": "A fully formatted message using Slack mrkdwn syntax with these bold sections: 1. Idea Title  2. Recommended Node Configuration  3. Implementation Difficulties  4. Ideas for Improvement  5. Alternative Ideas"
}

Do NOT include markdown fences or any text outside the JSON object."""


@log_mcp_call("tool", "ai_solution_architect")
def ai_solution_architect(idea_title: str) -> str:
    """Use GPT to design a complete n8n workflow plan for the given idea."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER")
    model = os.getenv("MODEL", "gpt-5.1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    user_prompt = (
        f"User Idea: {idea_title}\n\n"
        "Analyze this idea and output your response as a strictly valid JSON object "
        "(no markdown, no extra text). Follow the structure in the system prompt."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"

    # Strip possible markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        output = json.loads(raw)
    except json.JSONDecodeError:
        output = {
            "title": idea_title,
            "nodes": "Could not parse AI output",
            "challenges": "",
            "improvements": "",
            "alternatives": "",
            "slack_message": f"*AI Solution Architect*\n\nIdea: {idea_title}\n\nCould not parse structured response.",
        }

    return json.dumps({"output": output, "idea_title": idea_title})
