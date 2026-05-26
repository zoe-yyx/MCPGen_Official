"""
Logging utilities for MCP server.

Key rule: MCP server communicates via stdio JSON-RPC.
Any output to stdout/stderr breaks the protocol.
=> server-side loggers MUST be file-only (console_output=False).
=> workflow runner loggers MAY use console (console_output=True).
"""

import logging
import functools
import json
from pathlib import Path
from typing import Any, Callable
import asyncio


def setup_logging(log_file: str, console_output: bool = False) -> logging.Logger:
    """
    Create a logger that writes to *log_file* only.

    Args:
        log_file:       Path to the target log file (created if missing).
        console_output: Also stream to stderr (safe for workflow runner only).

    Returns:
        Configured logging.Logger instance.
    """
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(log_file)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # never leak into root / stdio

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        if console_output:
            import sys
            ch = logging.StreamHandler(sys.stderr)
            ch.setFormatter(fmt)
            logger.addHandler(ch)

    return logger


def log_tool_call(logger: logging.Logger) -> Callable:
    """
    Decorator factory — logs inputs and outputs of every tool call.

    Usage:
        @log_tool_call(logger)
        async def my_tool(x: int) -> str: ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            name = func.__name__
            try:
                preview = {k: (v if len(str(v)) <= 200 else str(v)[:200] + "…")
                           for k, v in kwargs.items()}
                logger.info(f"[CALL] {name} | {json.dumps(preview, ensure_ascii=False, default=str)}")
            except Exception:
                logger.info(f"[CALL] {name}")
            try:
                result = await func(*args, **kwargs)
                rs = str(result)
                logger.info(f"[DONE] {name} | {rs[:300]}{'…' if len(rs) > 300 else ''}")
                return result
            except Exception as exc:
                logger.error(f"[ERROR] {name} | {type(exc).__name__}: {exc}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            name = func.__name__
            try:
                preview = {k: (v if len(str(v)) <= 200 else str(v)[:200] + "…")
                           for k, v in kwargs.items()}
                logger.info(f"[CALL] {name} | {json.dumps(preview, ensure_ascii=False, default=str)}")
            except Exception:
                logger.info(f"[CALL] {name}")
            try:
                result = func(*args, **kwargs)
                rs = str(result)
                logger.info(f"[DONE] {name} | {rs[:300]}{'…' if len(rs) > 300 else ''}")
                return result
            except Exception as exc:
                logger.error(f"[ERROR] {name} | {type(exc).__name__}: {exc}")
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator