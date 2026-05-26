"""Tools for calling Polymarket public APIs (gamma-api and clob)."""

import httpx
from typing import Any
from .utils.log_decorator import log_mcp_call

GAMMA_API = "ENDPOINT_PLACEHOLDER"
CLOB_API = "ENDPOINT_PLACEHOLDER"


@log_mcp_call("tool", "find_event_id_from_slug")
async def find_event_id_from_slug(slug: str) -> dict[str, Any]:
    """Find the event ID from a Polymarket market slug.

    Args:
        slug: The slug of the Polymarket market (e.g. 'bitcoin-up-or-down-january-12-8am-et').

    Returns:
        dict with market data including events list.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{GAMMA_API}/markets/slug/{slug}")
        resp.raise_for_status()
        return resp.json()


@log_mcp_call("tool", "find_series_id_from_event")
async def find_series_id_from_event(event_id: str) -> dict[str, Any]:
    """Find the series ID from an event ID.

    Args:
        event_id: The Polymarket event ID.

    Returns:
        dict with event data including series list.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{GAMMA_API}/events/{event_id}")
        resp.raise_for_status()
        return resp.json()


@log_mcp_call("tool", "find_all_events_for_series")
async def find_all_events_for_series(series_id: str) -> dict[str, Any]:
    """Find all events belonging to a series.

    Args:
        series_id: The Polymarket series ID.

    Returns:
        dict with series data including events list.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{GAMMA_API}/series/{series_id}")
        resp.raise_for_status()
        return resp.json()


@log_mcp_call("tool", "fetch_up_down_tokens")
async def fetch_up_down_tokens(event_id: str) -> dict[str, Any]:
    """Fetch UP/DOWN token IDs and end time for an event.

    Args:
        event_id: The Polymarket event ID.

    Returns:
        dict with event data including markets with token IDs.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{GAMMA_API}/events/{event_id}")
        resp.raise_for_status()
        return resp.json()


@log_mcp_call("tool", "fetch_price_history")
async def fetch_price_history(token_id: str, start_ts: int, end_ts: int) -> dict[str, Any]:
    """Fetch historical price data for a token.

    Args:
        token_id: The CLOB token ID (UP token).
        start_ts: Start Unix timestamp.
        end_ts: End Unix timestamp.

    Returns:
        dict with history list of {t, p} entries.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CLOB_API}/prices-history",
            params={"market": token_id, "startTs": start_ts, "endTs": end_ts},
        )
        resp.raise_for_status()
        return resp.json()
