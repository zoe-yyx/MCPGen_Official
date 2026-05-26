"""Google Sheets tools: trigger/read candidate data from spreadsheet (mocked).

Simulates the Google Sheets Trigger node that polls for new hiring prospects.
"""

import json
import os

from .utils.log_decorator import log_mcp_call

# Mock data simulating the "Hiring Prospects" Google Sheet
MOCK_CANDIDATES = [
    {
        "NAME": "Alice Johnson",
        "EMAIL": "EMAIL_PLACEHOLDER",
        "EDUCATIONAL": "M.Sc. Computer Science, Stanford University. 3 years experience in backend development.",
    },
    {
        "NAME": "Bob Smith",
        "EMAIL": "EMAIL_PLACEHOLDER",
        "EDUCATIONAL": "B.Tech Information Technology, MIT. 2 years experience in full-stack development.",
    },
    {
        "NAME": "Carol Zhang",
        "EMAIL": "EMAIL_PLACEHOLDER",
        "EDUCATIONAL": "Ph.D. Data Science, UC Berkeley. 5 years experience in ML engineering.",
    },
]


@log_mcp_call("tool", "google_sheets_trigger")
def google_sheets_trigger(sheet_id: str = "", sheet_name: str = "") -> str:
    """Poll Google Sheets for new hiring prospect rows (mocked).

    Simulates the Google Sheets Trigger that watches for new rows
    in the 'Hiring Prospects' spreadsheet.

    Args:
        sheet_id: Google Sheet document ID (ignored in mock).
        sheet_name: Sheet tab name (ignored in mock).

    Returns:
        JSON string with a list of candidate records (NAME, EMAIL, EDUCATIONAL).
    """
    return json.dumps(MOCK_CANDIDATES)
