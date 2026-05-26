"""Tools for aggregating stock data and generating AI summary."""

import json
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from .utils.log_decorator import log_mcp_call

load_dotenv()


@log_mcp_call("tool", "aggregate_data")
def aggregate_data(stock_items: list[dict]) -> dict:
    """Aggregate all scraped stock items into a single data object.

    Args:
        stock_items: List of individual stock data dicts.

    Returns:
        Dict with 'data' key containing the full list.
    """
    return {"data": stock_items}


@log_mcp_call("tool", "create_summary")
def create_summary(aggregated_data: dict) -> dict:
    """Use LLM to generate a styled HTML email summary of daily stock performance.

    Args:
        aggregated_data: Dict with 'data' key containing list of stock records.

    Returns:
        Dict with 'html' (email body) and 'subject' (email subject).
    """
    api_key = os.getenv("API_KEY", "")
    base_url = os.getenv("BASE_URL", "")
    model = os.getenv("MODEL", "gpt-5.1")

    client = OpenAI(api_key=api_key, base_url=base_url)

    now_str = datetime.now().strftime("%A %Y-%m-%d %H:%M")
    data_json = json.dumps(aggregated_data["data"], indent=2, ensure_ascii=False)

    system_prompt = """## ROLE
You are a financial summary agent. Your role is to:
- Analyze incoming JSON data of top 10 U.S. stocks.
- Identify meaningful insights: trends, outliers, sentiment, sector behavior.
- Format this into a clear, styled HTML email body for professional users.
- Return ONLY a JSON object with two keys: "subject" and "html".

## TASKS
1. Analyze market trends based on price movements and sentiment.
2. Highlight top 2 gainers and losers, including reasoning from news or change %.
3. Generate a stock table (Ticker, Name, Price Change, Sentiment Icon).
4. Include 3-5 key takeaways, insights, or investor watch notes.
5. Format the HTML with inline styles, use semantic structure.
6. Use icons for sentiment: green circle for Positive, yellow circle for Neutral, red circle for Negative.
7. Footer: "Generated automatically by your AI-powered stock monitor"

## OUTPUT FORMAT
Return ONLY valid JSON:
{
  "subject": "Daily Stock Report for {date}",
  "html": "<html email body here>"
}

## CONSTRAINTS
- Output JSON only, no markdown wrapping
- HTML must use inline styles, no external CSS
- Must be mobile-friendly and professional"""

    user_prompt = f"""The day and date today is {now_str}

Here is today's data:

```
{data_json}
```

Generate the daily stock summary email. Return ONLY the JSON with "subject" and "html" keys."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    raw = response.choices[0].message.content

    # Parse the response
    try:
        cleaned = raw.strip()
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
        parsed = json.loads(cleaned)
        return {
            "subject": parsed.get("subject", f"Daily Stock Report - {now_str}"),
            "html": parsed.get("html", raw),
        }
    except (json.JSONDecodeError, Exception):
        return {
            "subject": f"Daily Stock Report - {now_str}",
            "html": raw,
        }
