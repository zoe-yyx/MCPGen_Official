"""Logging decorator for MCP tool functions."""

import functools
import inspect
import logging
import os
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def setup_logging(log_path: str) -> logging.Logger:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger("mcp_server")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def log_mcp_call(operation_type: str = "tool", name: str | None = None) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        label = name or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                logger = logging.getLogger("mcp_server")
                logger.debug("[%s] %s called | args=%s kwargs=%s", operation_type, label, args, kwargs)
                result = await func(*args, **kwargs)
                logger.debug("[%s] %s returned | %.200s", operation_type, label, result)
                return result
            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                logger = logging.getLogger("mcp_server")
                logger.debug("[%s] %s called | args=%s kwargs=%s", operation_type, label, args, kwargs)
                result = func(*args, **kwargs)
                logger.debug("[%s] %s returned | %.200s", operation_type, label, result)
                return result
            return sync_wrapper  # type: ignore[return-value]

    return decorator
