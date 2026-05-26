"""
Logging utilities for MCP server tools.
Provides setup_logging() and a log_tool_call decorator for tracing inputs/outputs.
"""

import functools
import logging
import os
from pathlib import Path
from typing import Any, Callable


def setup_logging(log_file: str, console_output: bool = False) -> logging.Logger:
    """
    Configure and return a named logger.

    Args:
        log_file:       Path to the log file (created if missing).
        console_output: If True, also emit to stdout. Set False for MCP servers
                        (stdio must stay clean for JSON-RPC).

    Returns:
        Configured Logger instance.
    """
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(log_file)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # never bubble up to root (keeps stdio clean)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    if console_output:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


def log_tool_call(logger: logging.Logger) -> Callable:
    """
    Decorator factory: wraps a tool function and logs its arguments and return value.

    Usage::

        @log_tool_call(logger)
        def my_tool(x: int) -> str: ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.debug(
                "CALL %s | args=%s kwargs=%s",
                func.__name__,
                _safe_repr(args),
                _safe_repr(kwargs),
            )
            try:
                result = func(*args, **kwargs)
                logger.debug(
                    "RETURN %s | result=%s",
                    func.__name__,
                    _safe_repr(result),
                )
                return result
            except Exception as exc:
                logger.error("ERROR %s | %s: %s", func.__name__, type(exc).__name__, exc)
                raise

        return wrapper

    return decorator


def _safe_repr(value: Any, max_len: int = 300) -> str:
    """Truncate long repr strings so logs stay readable."""
    r = repr(value)
    return r if len(r) <= max_len else r[:max_len] + "…"