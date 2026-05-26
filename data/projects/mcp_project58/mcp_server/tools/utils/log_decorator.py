import logging
import functools
import inspect
from typing import Any, Callable, TypeVar
from fastmcp import Context
import os

F = TypeVar("F", bound=Callable[..., Any])


def get_logger(name: str = "mcp_server") -> logging.Logger:
    """Get or create a logger instance."""
    return logging.getLogger(name)


def log_mcp_call(operation_type: str = "tool", name: str | None = None) -> Callable[[F], F]:
    """Decorator for logging MCP operations."""

    def decorator(func: F) -> F:
        logger = get_logger()
        operation_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                log_args = []
                log_kwargs = {}
                for i, arg in enumerate(args):
                    if not isinstance(arg, Context):
                        log_args.append(f"arg{i}={arg}")
                for key, value in kwargs.items():
                    if not isinstance(value, Context):
                        log_kwargs[key] = value
                args_str = ", ".join(log_args + [f"{k}={v}" for k, v in log_kwargs.items()])
                logger.info(f"{operation_type.title()} '{operation_name}' called with {args_str}")
                try:
                    result = await func(*args, **kwargs)
                    logger.info(f"{operation_type.title()} '{operation_name}' completed. Result: {str(result)[:200]}")
                    return result
                except Exception as e:
                    logger.error(f"{operation_type.title()} '{operation_name}' failed: {e}", exc_info=True)
                    raise

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                log_args = []
                log_kwargs = {}
                for i, arg in enumerate(args):
                    if not isinstance(arg, Context):
                        log_args.append(f"arg{i}={arg}")
                for key, value in kwargs.items():
                    if not isinstance(value, Context):
                        log_kwargs[key] = value
                args_str = ", ".join(log_args + [f"{k}={v}" for k, v in log_kwargs.items()])
                logger.info(f"{operation_type.title()} '{operation_name}' called with {args_str}")
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"{operation_type.title()} '{operation_name}' completed. Result: {str(result)[:200]}")
                    return result
                except Exception as e:
                    logger.error(f"{operation_type.title()} '{operation_name}' failed: {e}", exc_info=True)
                    raise

            return sync_wrapper

    return decorator


def setup_logging(log_url: str, console_output: bool = True) -> logging.Logger:
    """Setup logging configuration."""
    os.makedirs(os.path.dirname(log_url) if os.path.dirname(log_url) else "logs", exist_ok=True)
    logger = logging.getLogger("mcp_server")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    file_handler = logging.FileHandler(log_url, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger
