"""Tools for chart generation, data combining, and final report generation."""

import json
import urllib.parse
from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "generate_chart")
def generate_chart(market_data: list[dict]) -> dict:
    """Generate a QuickChart URL for gold vs equity price comparison.

    Args:
        market_data: List of merged records with date, goldPrice, equityPrice.

    Returns:
        Dict with labels, gold, equity arrays and chartUrl.
    """
    if not market_data or "error" in market_data[0]:
        return {
            "chartUrl": "",
            "error": market_data[0].get("error", "No chart data available"),
        }

    labels = [item["date"] for item in market_data]
    gold = [item["goldPrice"] for item in market_data]
    equity = [item["equityPrice"] for item in market_data]

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Gold",
                    "data": gold,
                    "borderColor": "#D4AF37",
                    "backgroundColor": "rgba(212,175,55,0.15)",
                    "borderWidth": 3,
                    "fill": True,
                    "tension": 0.45,
                },
                {
                    "label": "Equity",
                    "data": equity,
                    "borderColor": "#2E86DE",
                    "backgroundColor": "rgba(46,134,222,0.15)",
                    "borderWidth": 3,
                    "fill": True,
                    "tension": 0.45,
                },
            ],
        },
    }

    chart_url = (
        "ENDPOINT_PLACEHOLDER"
        + urllib.parse.quote(json.dumps(chart_config))
    )

    return {
        "labels": labels,
        "gold": gold,
        "equity": equity,
        "chartUrl": chart_url,
    }


@log_mcp_call("tool", "combine_ai_chart_data")
def combine_ai_chart_data(ai_data: dict, chart_data: dict) -> dict:
    """Merge parsed AI insights with chart data.

    Args:
        ai_data: Parsed AI output dict.
        chart_data: Chart generation result with chartUrl.

    Returns:
        Combined dict with all AI fields plus chartUrl.
    """
    combined = {**ai_data}
    combined["chartUrl"] = chart_data.get("chartUrl", chart_data.get("url", ""))
    return combined


@log_mcp_call("tool", "generate_final_report")
def generate_final_report(combined_data: dict) -> dict:
    """Generate an HTML report from combined AI insights and chart data.

    Args:
        combined_data: Dict with AI insights and chartUrl.

    Returns:
        Dict with all fields plus generated html string.
    """
    d = combined_data
    winner_color = "#d4af37" if d.get("winner") == "Gold" else "#3498db"

    html = f"""
<div style="font-family: Arial, sans-serif; background:#f5f7fa; padding:20px;">
  <div style="max-width:700px; margin:auto; background:white; border-radius:10px; padding:20px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
    <h1 style="text-align:center; color:#2c3e50;">Gold vs Equity Report</h1>
    <h2 style="text-align:center; color:{winner_color};">Winner: {d.get('winner', 'N/A')}</h2>
    <hr/>
    <h3>Summary</h3>
    <p>{d.get('summary', 'N/A')}</p>
    <h3>Market Insight</h3>
    <p>{d.get('reason', 'N/A')}</p>
    <h3>Investment Advice</h3>
    <p>{d.get('investmentAdvice', 'N/A')}</p>
    <hr/>
    <h3>Portfolio Allocation</h3>
    <div style="display:flex; justify-content:space-between;">
      <div style="background:#f1c40f; padding:10px; border-radius:8px; width:45%; text-align:center;">
        <b>Gold</b><br/>{d.get('goldAllocation', 'N/A')}%
      </div>
      <div style="background:#3498db; color:white; padding:10px; border-radius:8px; width:45%; text-align:center;">
        <b>Equity</b><br/>{d.get('equityAllocation', 'N/A')}%
      </div>
    </div>
    <h3 style="margin-top:20px;">Strategy</h3>
    <p>{d.get('strategy', 'N/A')}</p>
    <hr/>
    <h3>Performance Chart</h3>
    <div style="text-align:center;">
      <img src="{d.get('chartUrl', '')}" style="width:100%; border-radius:8px;" />
    </div>
    <p style="text-align:center; color:gray; font-size:12px; margin-top:20px;">
      Auto-generated financial insights report
    </p>
  </div>
</div>
"""
    return {**d, "html": html}
