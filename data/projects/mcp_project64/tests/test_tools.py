"""Unit tests for tool functions (no MCP dependency)."""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.data_tools import (
    convert_endtime_to_unix,
    extract_tokens_and_endtime,
    set_start_time,
    split_events,
    split_prices_and_timestamps,
)
from mcp_server.tools.utils.mock_storage import (
    insert_record,
    load_table,
    query_records,
    save_table,
    update_records,
)


# ── Data tools tests ──


def test_split_events():
    series_data = {
        "events": [
            {"id": "evt1", "closed": True},
            {"id": "evt2", "closed": False},
            {"id": "evt3", "closed": True},
        ]
    }
    result = split_events(series_data)
    assert len(result) == 3
    assert result[0] == {"id": "evt1", "closed": True}
    assert result[1] == {"id": "evt2", "closed": False}


def test_split_events_empty():
    assert split_events({}) == []
    assert split_events({"events": []}) == []


def test_extract_tokens_and_endtime():
    event_data = {
        "markets": [
            {
                "id": "market123",
                "endDate": "2025-01-12T13:00:00Z",
                "clobTokenIds": '["token_up_abc", "token_dw_xyz"]',
            }
        ]
    }
    result = extract_tokens_and_endtime(event_data)
    assert result["MarketId"] == "market123"
    assert result["EndTime"] == "2025-01-12T13:00:00Z"
    assert result["TokenUp"] == "token_up_abc"
    assert result["TokenDw"] == "token_dw_xyz"


def test_extract_tokens_list_format():
    event_data = {
        "markets": [
            {
                "id": "m1",
                "endDate": "2025-01-12T13:00:00Z",
                "clobTokenIds": ["up123", "dw456"],
            }
        ]
    }
    result = extract_tokens_and_endtime(event_data)
    assert result["TokenUp"] == "up123"
    assert result["TokenDw"] == "dw456"


def test_convert_endtime_to_unix():
    ts = convert_endtime_to_unix("2025-01-12T13:00:00Z")
    assert ts == 1736686800


def test_convert_endtime_with_offset():
    ts = convert_endtime_to_unix("2025-01-12T10:00:00-03:00")
    assert ts == 1736686800


def test_set_start_time():
    result = set_start_time(1736683200, 3600)
    assert result["EndTimeUnix"] == 1736683200
    assert result["StartTimeUnix"] == 1736683200 - 3600


def test_set_start_time_default():
    result = set_start_time(1000000)
    assert result["StartTimeUnix"] == 1000000 - 3600


def test_split_prices_and_timestamps():
    history = {
        "history": [
            {"t": 1000, "p": 0.55},
            {"t": 1060, "p": 0.58},
            {"t": 1120, "p": 0.60},
        ]
    }
    result = split_prices_and_timestamps(history)
    assert result["t"] == [1000, 1060, 1120]
    assert result["p"] == [0.55, 0.58, 0.60]


def test_split_prices_empty():
    result = split_prices_and_timestamps({})
    assert result["t"] == []
    assert result["p"] == []


# ── Mock storage tests ──


def test_mock_storage_crud():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump([], f)
        path = f.name

    try:
        # Insert
        insert_record(path, {"id": "a", "value": 1})
        insert_record(path, {"id": "b", "value": 2})

        # Load
        table = load_table(path)
        assert len(table) == 2

        # Query
        results = query_records(path, filter_fn=lambda r: r["id"] == "a")
        assert len(results) == 1
        assert results[0]["value"] == 1

        # Update
        count = update_records(path, "id", "a", {"value": 10})
        assert count == 1
        table = load_table(path)
        assert table[0]["value"] == 10

        # Limit
        results = query_records(path, limit=1)
        assert len(results) == 1
    finally:
        os.unlink(path)


# ── Storage tools tests ──


def test_register_and_fetch_events():
    """Test register_event and fetch_unprocessed_events with temp file."""
    import mcp_server.tools.storage_tools as st

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump([], f)
        path = f.name

    original_path = st.EVENT_TABLE_PATH
    st.EVENT_TABLE_PATH = path
    try:
        st.register_event("evt1", True)
        st.register_event("evt2", False)
        # Duplicate should not add
        st.register_event("evt1", True)

        table = load_table(path)
        assert len(table) == 2

        unprocessed = st.fetch_unprocessed_events(100)
        assert len(unprocessed) == 2

        st.mark_event_processed("evt1")
        unprocessed = st.fetch_unprocessed_events(100)
        assert len(unprocessed) == 1
        assert unprocessed[0]["EventId"] == "evt2"
    finally:
        st.EVENT_TABLE_PATH = original_path
        os.unlink(path)


def test_store_in_supabase():
    import mcp_server.tools.storage_tools as st

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump([], f)
        path = f.name

    original_path = st.SUPABASE_TABLE_PATH
    st.SUPABASE_TABLE_PATH = path
    try:
        st.store_in_supabase("evt1", [0.5, 0.6], [1000, 1060])
        table = load_table(path)
        assert len(table) == 1
        assert table[0]["EventId"] == "evt1"
        assert table[0]["price"] == [0.5, 0.6]
    finally:
        st.SUPABASE_TABLE_PATH = original_path
        os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
