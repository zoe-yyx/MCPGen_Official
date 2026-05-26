"""Form tools — simulate the n8n form trigger for URL submission."""

import json
import time

from mcp_server.tools.utils.log_decorator import log_mcp_call


@log_mcp_call(operation_type="tool")
def submit_form(url: str) -> str:
    """Simulate a web form submission with a Threads URL.

    Returns the submitted form data as JSON, matching what n8n's formTrigger produces.
    """
    if not url or not url.strip():
        raise ValueError("URL is required and cannot be empty.")
    return json.dumps({
        "URL": url.strip(),
        "submitted_at": int(time.time()),
        "form_title": "Threads Downloader",
    })
