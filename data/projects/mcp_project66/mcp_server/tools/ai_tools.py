"""AI tools: generate personalized interview invitation email using GPT."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()

SYSTEM_PROMPT = (
    "You are a helpful email writing assistant. You take the information I provide "
    "you with and write a personalized email to the candidate we are calling in for "
    "an interview. The goal is to send an email with Google Calendar Link. Be straight "
    "to the point. The email should start with a 15-20 word opening statement, then "
    "details to the link and then signature."
)


@log_mcp_call("tool", "generate_interview_email")
def generate_interview_email(
    candidate_name: str,
    candidate_education: str,
    calendar_link: str,
    sender_name: str = "",
    sender_company: str = "",
) -> str:
    """Generate a personalized interview invitation email using GPT.

    Args:
        candidate_name: Full name of the candidate.
        candidate_education: Educational background and experience.
        calendar_link: Google Calendar event link for the interview.
        sender_name: Name of the interviewer/sender.
        sender_company: Company name.

    Returns:
        JSON string with 'body' field containing the email text.
    """
    sender_name = sender_name or os.getenv("GMAIL_SENDER_NAME", "Surya")
    sender_company = sender_company or os.getenv("GMAIL_SENDER_COMPANY", "Techdome")

    user_prompt = (
        f"{candidate_name}\n\n"
        f"{candidate_education}\n\n"
        f"Link for calendar: {calendar_link}\n\n"
        f"My name is {sender_name}, I'm from {sender_company}"
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

    body = response.choices[0].message.content or ""
    return json.dumps({"body": body})
