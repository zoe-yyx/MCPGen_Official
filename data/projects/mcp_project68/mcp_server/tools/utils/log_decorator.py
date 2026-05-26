import logging
import functools
import inspect
from typing import Any, Callable, TypeVar
from fastmcp import Context
import os

F = TypeVar("F", bound=Callable[..., Any])


def get_logger(name: str = "mcp_server") -> logging.Logger:
    return logging.getLogger(name)


def log_mcp_call(operation_type: str = "tool", name: str = None) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        logger = get_logger()
        operation_name = name or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                log_kwargs = {k: v for k, v in kwargs.items() if not isinstance(v, Context)}
                logger.info(f"{operation_type.title()} '{operation_name}' called with {log_kwargs}")
                try:
                    result = await func(*args, **kwargs)
                    logger.info(f"{operation_type.title()} '{operation_name}' completed. Result: {result}")
                    return result
                except Exception as e:
                    logger.error(f"{operation_type.title()} '{operation_name}' failed: {e}", exc_info=True)
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                log_kwargs = {k: v for k, v in kwargs.items() if not isinstance(v, Context)}
                logger.info(f"{operation_type.title()} '{operation_name}' called with {log_kwargs}")
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"{operation_type.title()} '{operation_name}' completed. Result: {result}")
                    return result
                except Exception as e:
                    logger.error(f"{operation_type.title()} '{operation_name}' failed: {e}", exc_info=True)
                    raise
            return sync_wrapper
    return decorator


def setup_logging(log_url: str) -> logging.Logger:
    os.makedirs(os.path.dirname(log_url) if os.path.dirname(log_url) else ".", exist_ok=True)
    logger = logging.getLogger("mcp_server")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    file_handler = logging.FileHandler(log_url, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
