"""
Logging utility for MCP server and workflow runner.
MCP server must use file-only logging (no console) to preserve stdio JSON-RPC purity.
"""
import logging
import functools
import json
from pathlib import Path
from typing import Any, Callable


def setup_logging(log_file: str, console_output: bool = False) -> logging.Logger:
    """
    Set up a logger writing to file. Console output is opt-in (workflow runner only).

    Args:
        log_file: Path to the log file (e.g. "logs/server.log").
        console_output: If True, also emit to stdout. Must be False for MCP servers.
    Returns:
        Configured Logger instance.
    """
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(log_file)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # critical: never let logs bubble to root (breaks stdio)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
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
    Decorator that logs the inputs and outputs of every MCP tool function.

    Usage:
        @log_tool_call(logger)
        def my_tool(param: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            func_name = func.__name__
            try:
                safe_kwargs = {
                    k: ("<binary>" if isinstance(v, bytes) else v)
                    for k, v in kwargs.items()
                }
                logger.debug(
                    "CALL  %s | args=%s kwargs=%s",
                    func_name,
                    args,
                    json.dumps(safe_kwargs, default=str, ensure_ascii=False),
                )
            except Exception:
                logger.debug("CALL  %s | (could not serialise args)", func_name)

            try:
                result = func(*args, **kwargs)
                try:
                    logger.debug(
                        "RETURN %s | %s",
                        func_name,
                        json.dumps(result, default=str, ensure_ascii=False)[:500],
                    )
                except Exception:
                    logger.debug("RETURN %s | (non-serialisable result)", func_name)
                return result
            except Exception as exc:
                logger.error("ERROR  %s | %s: %s", func_name, type(exc).__name__, exc)
                raise

        return wrapper
    return decorator