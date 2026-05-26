import logging
import functools
import inspect
from typing import Any, Callable, TypeVar
from fastmcp import Context
import os

F = TypeVar("F", bound=Callable[..., Any])


def get_logger(name: str = "mcp_server") -> logging.Logger:
    return logging.getLogger(name)


def log_mcp_call(operation_type: str = "tool", name: str | None = None) -> Callable[[F], F]:
    """Decorator for logging MCP tool/resource/prompt calls."""

    def decorator(func: F) -> F:
        logger = get_logger()
        operation_name = name or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                log_args = [f"arg{i}={a}" for i, a in enumerate(args) if not isinstance(a, Context)]
                log_kwargs = {k: v for k, v in kwargs.items() if not isinstance(v, Context)}
                args_str = ", ".join(log_args + [f"{k}={v}" for k, v in log_kwargs.items()])
                logger.info(f"{operation_type.title()} '{operation_name}' called with {args_str[:200]}")
                try:
                    result = await func(*args, **kwargs)
                    logger.info(f"{operation_type.title()} '{operation_name}' completed. Result: {str(result)[:200]}")
                    return result
                except Exception as e:
                    logger.error(f"{operation_type.title()} '{operation_name}' failed: {e}", exc_info=True)
                    raise
            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                log_args = [f"arg{i}={a}" for i, a in enumerate(args) if not isinstance(a, Context)]
                log_kwargs = {k: v for k, v in kwargs.items() if not isinstance(v, Context)}
                args_str = ", ".join(log_args + [f"{k}={v}" for k, v in log_kwargs.items()])
                logger.info(f"{operation_type.title()} '{operation_name}' called with {args_str[:200]}")
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"{operation_type.title()} '{operation_name}' completed. Result: {str(result)[:200]}")
                    return result
                except Exception as e:
                    logger.error(f"{operation_type.title()} '{operation_name}' failed: {e}", exc_info=True)
                    raise
            return sync_wrapper  # type: ignore

    return decorator


def setup_logging(log_url: str) -> logging.Logger:
    """Setup logging for the MCP server."""
    os.makedirs(os.path.dirname(log_url) if os.path.dirname(log_url) else "logs", exist_ok=True)
    logger = logging.getLogger("mcp_server")
    logger.setLevel(logging.INFO)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    fh = logging.FileHandler(log_url, encoding="utf-8")
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
