"""Tools for calculating performance metrics and generating AI insights."""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv
from .utils.log_decorator import log_mcp_call

load_dotenv()


@log_mcp_call("tool", "calculate_performance_metrics")
def calculate_performance_metrics(market_data: list[dict]) -> dict:
    """Calculate gold vs equity return metrics from merged market data.

    Args:
        market_data: List of merged records with date, goldPrice, equityPrice.

    Returns:
        Dict with startDate, endDate, goldReturn, equityReturn, difference, winner.
    """
    if not market_data or "error" in market_data[0]:
        return {"error": market_data[0].get("error", "No data available")}

    first = market_data[0]
    last = market_data[-1]

    gold_return = ((last["goldPrice"] - first["goldPrice"]) / first["goldPrice"]) * 100
    equity_return = ((last["equityPrice"] - first["equityPrice"]) / first["equityPrice"]) * 100
    diff = gold_return - equity_return

    winner = "Equal"
    if diff > 0:
        winner = "Gold"
    elif diff < 0:
        winner = "Equity"

    return {
        "startDate": first["date"],
        "endDate": last["date"],
        "goldReturn": f"{gold_return:.2f}",
        "equityReturn": f"{equity_return:.2f}",
        "difference": f"{diff:.2f}",
        "winner": winner,
    }


@log_mcp_call("tool", "generate_ai_investment_insights")
def generate_ai_investment_insights(metrics: dict) -> str:
    """Use LLM to generate investment insights from performance metrics.

    Args:
        metrics: Performance metrics dict with returns and winner.

    Returns:
        Raw AI output string (JSON format).
    """
    api_key = os.getenv("API_KEY", "")
    base_url = os.getenv("BASE_URL", "")

    model = os.getenv("MODEL", "gpt-5.1")
    client = OpenAI(api_key=api_key, base_url=base_url)

    user_prompt = (
        f"Analyze the following asset performance:\n\n"
        f"Start Date: {metrics['startDate']}\n"
        f"End Date: {metrics['endDate']}\n\n"
        f"Gold Return: {metrics['goldReturn']}%\n"
        f"Equity Return: {metrics['equityReturn']}%\n"
        f"Difference: {metrics['difference']}%"
    )

    system_prompt = (
        "You are a financial analyst and investment advisor.\n\n"
        "Your job:\n"
        "1. Compare gold vs equity performance\n"
        "2. Explain why one performed better\n"
        "3. Suggest portfolio allocation based on returns\n\n"
        "Rules:\n"
        "- Use exact numbers provided\n"
        "- Do NOT give generic advice\n"
        "- Allocation must total 100%\n"
        "- Keep reasoning realistic and data-driven\n\n"
        "Output ONLY valid JSON:\n\n"
        "{\n"
        '  "summary": "clear comparison with numbers",\n'
        '  "winner": "Gold or Equity",\n'
        '  "reason": "why one outperformed",\n'
        '  "investmentAdvice": "specific actionable advice",\n'
        '  "goldAllocation": "percentage number",\n'
        '  "equityAllocation": "percentage number",\n'
        '  "strategy": "why this allocation makes sense"\n'
        "}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content


@log_mcp_call("tool", "parse_ai_output")
def parse_ai_output(raw_output: str) -> dict:
    """Parse the raw AI output string into a structured dict.

    Args:
        raw_output: Raw JSON string from AI.

    Returns:
        Parsed dict with summary, winner, reason, investmentAdvice, allocations, strategy.
    """
    try:
        # Try to extract JSON from possible markdown code blocks
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.strip().startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)
        return json.loads(cleaned)
    except (json.JSONDecodeError, Exception):
        return {
            "error": "Invalid JSON from AI",
            "rawOutput": raw_output,
        }
