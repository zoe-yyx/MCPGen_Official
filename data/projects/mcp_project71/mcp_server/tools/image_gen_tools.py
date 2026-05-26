"""Image generation mock tools for mcp_project71 — Nano Banana Pro / kie.ai."""

import json
import uuid
from datetime import datetime

from .utils.log_decorator import log_mcp_call

# In-memory job store for mock
_JOB_STORE: dict[str, dict] = {}

# Placeholder public image URL used by mock (small PNG hosted by placehold.co)
_MOCK_IMAGE_URL = "ENDPOINT_PLACEHOLDER"


@log_mcp_call("tool", "submit_image_generation")
def submit_image_generation(prompt: str) -> str:
    """Mock kie.ai createTask: submit image generation job and return task/record IDs."""
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    record_id = f"rec-{uuid.uuid4().hex[:8]}"
    _JOB_STORE[task_id] = {
        "taskId": task_id,
        "recordId": record_id,
        "prompt": prompt,
        "state": "pending",
        "created_at": datetime.now().isoformat(),
    }
    return json.dumps({
        "code": 200,
        "data": {
            "taskId": task_id,
            "recordId": record_id,
        },
    })


@log_mcp_call("tool", "wait_for_processing")
def wait_for_processing(seconds: int = 10) -> str:
    """Simulate a wait period (returns immediately in mock)."""
    return json.dumps({"waited_seconds": seconds, "status": "completed"})


@log_mcp_call("tool", "check_job_status")
def check_job_status(task_id: str, record_id: str) -> str:
    """Mock kie.ai recordInfo: return job status. Always succeeds in mock."""
    job = _JOB_STORE.get(task_id, {})

    result_json = json.dumps({
        "resultUrls": [_MOCK_IMAGE_URL],
        "prompt": job.get("prompt", ""),
    })

    return json.dumps({
        "code": 200,
        "data": {
            "taskId": task_id,
            "recordId": record_id,
            "state": "success",
            "failMsg": None,
            "resultJson": result_json,
        },
    })


@log_mcp_call("tool", "wait_for_generation")
def wait_for_generation(seconds: int = 10) -> str:
    """Simulate a second wait period (returns immediately in mock)."""
    return json.dumps({"waited_seconds": seconds, "status": "completed"})


@log_mcp_call("tool", "parse_result")
def parse_result(status_response_json: str) -> str:
    """Parse job status response and extract the generated image URL."""
    response = json.loads(status_response_json)
    data = response.get("data", {})

    if response.get("code") != 200 or not data:
        return json.dumps({"status": "error", "message": "Invalid API response"})

    state = data.get("state", "")

    if state == "success":
        try:
            result_data = json.loads(data.get("resultJson", "{}"))
            result_urls = result_data.get("resultUrls", [])
            image_url = result_urls[0] if result_urls else None
        except (json.JSONDecodeError, IndexError):
            image_url = None

        if image_url:
            return json.dumps({
                "imageUrl": image_url,
                "taskId": data.get("taskId"),
                "status": "completed",
            })
        return json.dumps({"status": "error", "message": "No image URL in result"})

    elif state == "fail":
        raise RuntimeError(f"Image generation failed: {data.get('failMsg')}")
    else:
        return json.dumps({"status": "processing"})
