"""Logging decorator for MCP tool functions."""

import functools
import json
import logging
import os
from typing import Any, Callable


def setup_logging(log_path: str) -> logging.Logger:
    os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else ".", exist_ok=True)
    logger = logging.getLogger(log_path)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger


def log_mcp_call(operation_type: str = "tool", name: str | None = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger("mcp_tool")
            logger.debug("[%s] %s called args=%s kwargs=%s", operation_type, tool_name, args, kwargs)
            result = func(*args, **kwargs)
            logger.debug("[%s] %s returned %s", operation_type, tool_name, str(result)[:200])
            return result

        return wrapper

    return decorator
