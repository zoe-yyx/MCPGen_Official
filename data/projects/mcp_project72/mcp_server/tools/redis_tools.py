"""Redis mock tools for mcp_project72 — in-memory model assignment store."""

import json
import time
from typing import Any

from .utils.log_decorator import log_mcp_call

# In-memory Redis mock: {key: (value, expiry_timestamp)}
_STORE: dict[str, tuple[Any, float]] = {}


def _redis_get(key: str) -> Any:
    record = _STORE.get(key)
    if record is None:
        return None
    value, expiry = record
    if expiry > 0 and time.time() > expiry:
        del _STORE[key]
        return None
    return value


def _redis_set(key: str, value: Any, ttl: int = 0) -> None:
    expiry = (time.time() + ttl) if ttl > 0 else 0
    _STORE[key] = (value, expiry)


@log_mcp_call("tool", "check_user_model")
def check_user_model(wa_id: str) -> str:
    """Mock Redis GET: retrieve the current model index for a WhatsApp user."""
    key = f"llm-user:{wa_id}"
    value = _redis_get(key)
    return json.dumps({"key": key, "value": value, "found": value is not None})


@log_mcp_call("tool", "store_user_model")
def store_user_model(wa_id: str, model_index: int) -> str:
    """Mock Redis SET: store model index for a WhatsApp user (TTL=3600s)."""
    key = f"llm-user:{wa_id}"
    payload = json.dumps({"modelIndex": model_index})
    _redis_set(key, payload, ttl=3600)
    return json.dumps({
        "key": key,
        "model_index": model_index,
        "ttl": 3600,
        "status": "mock_set",
    })
