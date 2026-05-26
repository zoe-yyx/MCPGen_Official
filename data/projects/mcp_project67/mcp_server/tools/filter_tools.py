"""Filter tools: route candidates based on qualification and interview recommendation.

Converted from n8n Filter nodes.
"""

import json

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "filter_qualified")
def filter_qualified(assessment_data: str) -> str:
    """Filter to pass only qualified candidates (recommendation != Reject).

    Args:
        assessment_data: JSON string with 'recommendation' field from AI assessment.

    Returns:
        JSON string with 'passed' boolean and the original data.
    """
    data = json.loads(assessment_data)
    recommendation = data.get("recommendation", "Reject")
    passed = recommendation != "Reject"
    return json.dumps({"passed": passed, "data": data})


@log_mcp_call("tool", "filter_interview")
def filter_interview(assessment_data: str) -> str:
    """Filter to pass only candidates recommended for formal interview.

    Args:
        assessment_data: JSON string with 'recommendation' field.

    Returns:
        JSON string with 'passed' boolean and the original data.
    """
    data = json.loads(assessment_data)
    recommendation = data.get("recommendation", "")
    passed = recommendation == "Interview"
    return json.dumps({"passed": passed, "data": data})
