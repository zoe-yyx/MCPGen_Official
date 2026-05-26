"""AI demand forecasting tool — Step 5."""

import json
import os

from openai import OpenAI

from .utils.log_decorator import log_mcp_call

_SYSTEM_PROMPT = """\
You are an inventory demand forecasting AI. Given a product's current stock levels,
reorder point, and sales velocity data, determine whether a reorder is needed and
how much to order. Respond ONLY with a valid JSON object in exactly this format:
{
  "should_reorder": <true|false>,
  "recommended_quantity": <integer>,
  "days_until_stockout": <integer>,
  "forecasted_demand_30days": <integer>,
  "confidence_level": <"high"|"medium"|"low">,
  "reasoning": "<one sentence explanation>"
}
"""


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER"),
    )


@log_mcp_call(operation_type="tool")
def ai_demand_forecasting(product_data_json: str) -> str:
    """Call GPT to forecast demand and determine if reordering is needed.

    Args:
        product_data_json: JSON string with merged product + sales data

    Returns:
        JSON string with 'forecast' key containing the AI's JSON forecast.
    """
    product = json.loads(product_data_json)
    model = os.environ.get("MODEL", "gpt-5.1")

    user_message = (
        f"Product: {product.get('product_name')} ({product.get('product_id')})\n"
        f"Current stock: {product.get('current_stock')} units\n"
        f"Reorder point: {product.get('reorder_point')} units\n"
        f"Units sold (last 30 days): {product.get('units_sold_30days')}\n"
        f"Avg daily sales: {product.get('avg_daily_sales')}\n"
        f"Sales trend: {product.get('trend')}\n"
        f"Lead time: {product.get('lead_time_days')} days\n"
        f"Unit cost: ${product.get('unit_cost')}\n"
        "\nShould we reorder? If yes, how much?"
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    forecast_str = response.choices[0].message.content or "{}"
    try:
        forecast = json.loads(forecast_str)
    except json.JSONDecodeError:
        forecast = {
            "should_reorder": False,
            "recommended_quantity": 0,
            "days_until_stockout": 999,
            "forecasted_demand_30days": 0,
            "confidence_level": "low",
            "reasoning": "Failed to parse AI response",
        }

    return json.dumps({
        "product_id": product.get("product_id"),
        "forecast": forecast,
        "model": model,
        "raw_response": forecast_str,
    })
