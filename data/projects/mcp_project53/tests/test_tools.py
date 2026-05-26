"""
tests/test_tools.py
====================
Unit tests for all MCP tool functions — no MCP transport, direct Python calls.
"""
import json
import sys
import shutil
import tempfile
from pathlib import Path

# ── Ensure project root is importable ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from mcp_server.tools.validation_tools import tool_validate_and_enrich
from mcp_server.tools.storage_tools import (
    tool_check_duplicate,
    tool_find_or_create_folder,
    tool_upload_document,
    tool_find_employee_record,
    tool_upsert_employee_record,
)
from mcp_server.tools.notification_tools import (
    tool_upload_to_cdn,
    tool_send_confirmation_email,
    tool_build_final_response,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def isolated_results(tmp_path, monkeypatch):
    """Redirect all file I/O to a temporary directory for test isolation."""
    import mcp_server.tools.storage_tools as st
    import mcp_server.tools.notification_tools as nt

    st._RESULTS_DIR = tmp_path / "results" / "outputs"
    st._DB_FILE = st._RESULTS_DIR / "airtable.json"
    st._CONTRACTS_DIR = st._RESULTS_DIR / "contracts"
    nt._CDN_STAGING_DIR = tmp_path / "cdn_staging"

    yield


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    f = tmp_path / "contract.pdf"
    f.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\nstartxref\n%%EOF\n"
    )
    return f


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Tool
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateAndEnrich:
    def test_basic_success(self):
        raw = tool_validate_and_enrich(
            employee_name="sarah johnson",
            filename="contract.pdf",
            employee_id="emp-0042",
            contract_type="Full-Time Employment",
            department="Engineering",
            effective_date="2025-03-01",
        )
        data = json.loads(raw)
        assert data["employeeName"] == "Sarah Johnson"
        assert data["employeeId"] == "EMP-0042"
        assert data["structuredFilename"] == "EMP-0042_JOHNSON_FULL-TIME-EMPLOYMENT_2025-03-01.pdf"
        assert data["driveFolderPath"] == "HR/Contracts/2025/Engineering/Sarah Johnson"

    def test_missing_employee_name_raises(self):
        with pytest.raises(ValueError, match="employeeName"):
            tool_validate_and_enrich(employee_name="", filename="doc.pdf")

    def test_missing_file_source_raises(self):
        with pytest.raises(ValueError, match="file_url"):
            tool_validate_and_enrich(employee_name="Alice")

    def test_invalid_extension_raises(self):
        with pytest.raises(ValueError, match="not allowed"):
            tool_validate_and_enrich(employee_name="Alice", filename="file.exe")

    def test_auto_employee_id(self):
        raw = tool_validate_and_enrich(employee_name="Bob Smith", filename="c.pdf")
        data = json.loads(raw)
        assert data["employeeId"].startswith("EMP-")

    def test_file_url_path(self):
        raw = tool_validate_and_enrich(
            employee_name="Alice Wong",
            file_url="ENDPOINT_PLACEHOLDER",
        )
        data = json.loads(raw)
        assert data["fileUrl"] == "ENDPOINT_PLACEHOLDER"
        assert data["ext"] == "pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# Storage Tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestDuplicateCheck:
    def test_no_duplicate_initially(self):
        raw = tool_check_duplicate("EMP-0042")
        data = json.loads(raw)
        assert data["isDuplicate"] is False
        assert data["existingRecord"] is None

    def test_duplicate_after_upsert(self):
        tool_upsert_employee_record(
            employee_id="EMP-0042",
            employee_name="Sarah Johnson",
            department="Engineering",
            contract_type="Full-Time Employment",
            effective_date="2025-03-01",
            drive_url="file:///test",
            cdn_backup_url="file:///cdn",
            drive_folder_path="HR/Contracts/2025/Engineering/Sarah Johnson",
            structured_filename="EMP-0042_JOHNSON_...",
            filed_by="HR System",
            filed_at="2025-03-01T10:00:00+00:00",
        )
        raw = tool_check_duplicate("EMP-0042")
        data = json.loads(raw)
        assert data["isDuplicate"] is True


class TestFolderManagement:
    def test_creates_folder(self, tmp_path):
        import mcp_server.tools.storage_tools as st
        st._CONTRACTS_DIR = tmp_path / "contracts"

        raw = tool_find_or_create_folder("HR/Contracts/2025/Engineering/Alice")
        data = json.loads(raw)
        assert data["created"] is True
        assert Path(data["folderPath"]).exists()

    def test_idempotent_second_call(self, tmp_path):
        import mcp_server.tools.storage_tools as st
        st._CONTRACTS_DIR = tmp_path / "contracts"

        tool_find_or_create_folder("HR/Contracts/2025/Engineering/Alice")
        raw2 = tool_find_or_create_folder("HR/Contracts/2025/Engineering/Alice")
        data2 = json.loads(raw2)
        assert data2["created"] is False


class TestUploadDocument:
    def test_uploads_file(self, sample_pdf, tmp_path):
        dest_dir = tmp_path / "folder"
        dest_dir.mkdir()
        raw = tool_upload_document(
            source_path=str(sample_pdf),
            structured_filename="EMP-0042_JOHNSON_FTE_2025-03-01.pdf",
            folder_path=str(dest_dir),
        )
        data = json.loads(raw)
        assert Path(data["storedPath"]).exists()
        assert data["fileSizeBytes"] > 0

    def test_missing_source_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tool_upload_document(
                source_path="/nonexistent/file.pdf",
                structured_filename="x.pdf",
                folder_path=str(tmp_path),
            )


class TestEmployeeRecord:
    def test_find_returns_none_when_empty(self):
        raw = tool_find_employee_record("EMP-9999")
        data = json.loads(raw)
        assert data["recordExists"] is False

    def test_upsert_then_find(self):
        tool_upsert_employee_record(
            employee_id="EMP-0001",
            employee_name="Test User",
            department="QA",
            contract_type="Part-Time",
            effective_date="2025-01-01",
            drive_url="file:///x",
            cdn_backup_url="file:///y",
            drive_folder_path="HR/Contracts/2025/QA/Test User",
            structured_filename="EMP-0001_USER_PART-TIME_2025-01-01.pdf",
            filed_by="system",
            filed_at="2025-01-01T00:00:00+00:00",
        )
        raw = tool_find_employee_record("EMP-0001")
        data = json.loads(raw)
        assert data["recordExists"] is True
        assert data["record"]["employeeName"] == "Test User"

    def test_upsert_updates_existing(self):
        # First insert
        r1 = json.loads(tool_upsert_employee_record(
            employee_id="EMP-0001",
            employee_name="Test User",
            department="QA",
            contract_type="Part-Time",
            effective_date="2025-01-01",
            drive_url="file:///v1",
            cdn_backup_url="file:///cdn1",
            drive_folder_path="HR/C",
            structured_filename="f1.pdf",
            filed_by="sys",
            filed_at="2025-01-01T00:00:00+00:00",
        ))
        # Update
        r2 = json.loads(tool_upsert_employee_record(
            employee_id="EMP-0001",
            employee_name="Test User",
            department="QA",
            contract_type="Full-Time",
            effective_date="2025-06-01",
            drive_url="file:///v2",
            cdn_backup_url="file:///cdn2",
            drive_folder_path="HR/C",
            structured_filename="f2.pdf",
            filed_by="sys",
            filed_at="2025-06-01T00:00:00+00:00",
            record_id=r1["id"],
        ))
        assert r2["operation"] == "updated"
        assert r2["fields"]["contractType"] == "Full-Time"


# ═══════════════════════════════════════════════════════════════════════════════
# Notification Tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestCDNUpload:
    def test_upload_local_file(self, sample_pdf):
        raw = tool_upload_to_cdn(
            file_path=str(sample_pdf),
            structured_filename="test_upload.pdf",
        )
        data = json.loads(raw)
        assert data["cdnUrl"].startswith("file://")
        assert data["fileSizeBytes"] > 0

    def test_no_source_raises(self):
        with pytest.raises(ValueError):
            tool_upload_to_cdn(structured_filename="x.pdf")


class TestConfirmationEmail:
    def test_writes_email_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        raw = tool_send_confirmation_email(
            employee_name="Sarah Johnson",
            employee_id="EMP-0042",
            employee_email="EMAIL_PLACEHOLDER",
            department="Engineering",
            contract_type="Full-Time Employment",
            effective_date="2025-03-01",
            structured_filename="EMP-0042_JOHNSON_FTE_2025-03-01.pdf",
            drive_url="file:///drive/x.pdf",
            cdn_backup_url="file:///cdn/x.pdf",
            filed_by="HR System",
            filed_at="2025-03-01T10:00:00+00:00",
            notify_employee=False,
        )
        data = json.loads(raw)
        assert Path(data["emailFile"]).exists()
        assert data["method"] == "file"


class TestBuildFinalResponse:
    def test_success_response(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        raw = tool_build_final_response(
            employee_id="EMP-0042",
            employee_name="Sarah Johnson",
            department="Engineering",
            structured_filename="EMP-0042_JOHNSON_FTE_2025-03-01.pdf",
            contract_type="Full-Time Employment",
            effective_date="2025-03-01",
            drive_file_id="abc123",
            drive_url="file:///drive/x.pdf",
            drive_folder_path="HR/Contracts/2025/Engineering/Sarah Johnson",
            cdn_backup_url="file:///cdn/x.pdf",
            airtable_record_id="rec001",
            filed_by="HR System",
            filed_at="2025-03-01T10:00:00+00:00",
        )
        data = json.loads(raw)
        assert data["success"] is True
        assert "auditTrail" in data
        assert data["employeeId"] == "EMP-0042"