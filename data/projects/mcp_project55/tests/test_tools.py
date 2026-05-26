"""Unit tests for QR Ticket Scanner tools - direct function calls without MCP."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.tools.processing_tools import select_latest_item, set_ticket_code
from mcp_server.tools.validation_tools import validate_ticket
from mcp_server.tools.sheets_tools import (
    get_form_responses,
    read_ticket_rows,
    append_scan_result,
    _read_json,
    _write_json,
    SCAN_RESULTS_PATH,
)


class TestSelectLatestItem:
    def test_returns_last_item(self):
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = select_latest_item(items)
        assert result == {"id": 3}

    def test_single_item(self):
        result = select_latest_item([{"id": 1}])
        assert result == {"id": 1}

    def test_empty_list(self):
        result = select_latest_item([])
        assert result == {}


class TestSetTicketCode:
    def test_extracts_code(self):
        result = set_ticket_code("TKT-001-ABC")
        assert result == {"kode_tiket": "TKT-001-ABC"}

    def test_empty_code(self):
        result = set_ticket_code("")
        assert result == {"kode_tiket": ""}


class TestValidateTicket:
    def test_valid_ticket(self):
        rows = [{"TIKET": "TKT-001-ABC", "NAMA": "Ahmad"}]
        result = validate_ticket("TKT-001-ABC", rows)
        assert result["status"] == "VALID"
        assert result["matched_record"]["TIKET"] == "TKT-001-ABC"

    def test_invalid_ticket_no_match(self):
        rows = [{"TIKET": "TKT-001-ABC"}]
        result = validate_ticket("TKT-INVALID-999", rows)
        assert result["status"] == "TIDAK VALID"
        assert result["matched_record"] is None

    def test_invalid_ticket_empty_rows(self):
        result = validate_ticket("TKT-001-ABC", [])
        assert result["status"] == "TIDAK VALID"

    def test_multiple_rows_match_first(self):
        rows = [
            {"TIKET": "TKT-001-ABC", "NAMA": "Ahmad"},
            {"TIKET": "TKT-002-DEF", "NAMA": "Siti"},
        ]
        result = validate_ticket("TKT-002-DEF", rows)
        assert result["status"] == "VALID"
        assert result["matched_record"]["NAMA"] == "Siti"


class TestReadTicketRows:
    def test_finds_existing_ticket(self):
        rows = read_ticket_rows("TKT-001-ABC")
        assert len(rows) == 1
        assert rows[0]["NAMA"] == "Ahmad Rizky"

    def test_no_match(self):
        rows = read_ticket_rows("NONEXISTENT")
        assert rows == []


class TestGetFormResponses:
    def test_returns_responses(self):
        responses = get_form_responses()
        assert isinstance(responses, list)
        assert len(responses) >= 1


class TestAppendScanResult:
    def setup_method(self):
        """Reset scan results before each test."""
        _write_json(SCAN_RESULTS_PATH, [])

    def test_append_valid(self):
        record = append_scan_result(
            ticket_id="1",
            nama="Ahmad Rizky",
            email="EMAIL_PLACEHOLDER",
            no_hp="08123",
            tiket="TKT-001-ABC",
            status="VALID",
            ukuran_jersey="L",
            golongan_darah="O",
        )
        assert record["STATUS"] == "VALID"
        assert record["TIKET"] == "TKT-001-ABC"
        results = _read_json(SCAN_RESULTS_PATH)
        assert len(results) == 1

    def test_append_invalid(self):
        record = append_scan_result(
            ticket_id="-",
            nama="-",
            email="-",
            no_hp="-",
            tiket="TKT-INVALID",
            status="TIDAK VALID",
            ukuran_jersey="-",
            golongan_darah="-",
        )
        assert record["STATUS"] == "TIDAK VALID"
        assert record["NAMA"] == "-"

    def test_append_multiple(self):
        append_scan_result("1", "A", "a@b", "0", "T1", "VALID", "M", "A")
        append_scan_result("-", "-", "-", "-", "T2", "TIDAK VALID", "-", "-")
        results = _read_json(SCAN_RESULTS_PATH)
        assert len(results) == 2

    def teardown_method(self):
        """Clean up scan results after each test."""
        _write_json(SCAN_RESULTS_PATH, [])


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
