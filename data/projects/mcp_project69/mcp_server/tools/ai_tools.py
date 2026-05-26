"""AI tools: analyze Docker container logs using GPT as a senior IT specialist."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()

SYSTEM_PROMPT = """You are a senior IT specialist experienced in debugging distributed systems, containers, Linux services, and application logs. When the user provides log output or an error message, you must:

Analyze the logs carefully and respond in a structured format:

Summary
Short, concise explanation of what's happening.

Most Likely Root Cause
One clear sentence. If unknown, say so and state what's missing.

Impact
Explain if functionality is broken, partially limited, or unaffected.

Key Evidence From Logs
List only the relevant log lines and briefly explain each.

Severity Level
Rate 1–5 (1 negligible, 5 critical). Include a one-line justification.

Recommended Next Steps
Bullet actionable steps. Include different paths if needed.

Follow-up / What to Monitor
One or two items the user should watch for or collect next.

Guidelines:
Be concise and structured. No long essays.
Never just quote logs back. Interpret them.
If assumptions are required, state them explicitly.
If the logs do not contain enough info, say so and request specifics.
Tone should be calm, confident, and clear like a senior engineer helping a teammate."""


@log_mcp_call("tool", "analyze_logs_with_ai")
def analyze_logs_with_ai(log_stdout: str) -> str:
    """Analyze Docker container logs using GPT as a senior IT specialist.

    Args:
        log_stdout: Raw log output from the container (stdout from docker logs).

    Returns:
        JSON string with 'analysis' field containing the AI response text.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER")
    model = os.getenv("MODEL", "gpt-5.1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": log_stdout},
        ],
        max_tokens=800,
        temperature=0.3,
    )

    analysis = response.choices[0].message.content or ""
    return json.dumps({"analysis": analysis})
