"""Model decider tool for mcp_project72 — alternates GPT model index per user."""

import json

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "decide_model")
def decide_model(redis_value: str | None = None) -> str:
    """Alternate between model index 0 and 1 based on the previous Redis value.

    If no previous record exists, default to model 0.
    On each call, flip: 0→1, 1→0.
    """
    model_index = 0
    if redis_value:
        try:
            data = json.loads(redis_value) if isinstance(redis_value, str) else None
            if data and isinstance(data.get("modelIndex"), int):
                prev = data["modelIndex"]
                model_index = 1 if prev == 0 else 0
        except (json.JSONDecodeError, AttributeError):
            model_index = 0

    # In this mock we always use the same underlying GPT model,
    # but track the index for load-balancing simulation.
    model_names = ["gpt-5.1-primary", "gpt-5.1-secondary"]
    return json.dumps({
        "model_index": model_index,
        "model_name": model_names[model_index],
        "should_set": True,
    })
