"""Google Drive tools — mock upload and sharing permission management."""

import json
import os
import shutil
import time
import uuid

from mcp_server.tools.utils.log_decorator import log_mcp_call

_DRIVE_STORE = os.path.join("results", "outputs", "mock_drive")


@log_mcp_call(operation_type="tool")
def upload_video_to_drive(local_video_path: str, filename: str | None = None) -> str:
    """Upload a video file to Google Drive (mock — copies to results/outputs/mock_drive/).

    Returns metadata matching the Google Drive Files resource shape,
    including id, name, and webViewLink.
    """
    os.makedirs(_DRIVE_STORE, exist_ok=True)

    if not filename:
        filename = os.path.basename(local_video_path)

    drive_file_id = str(uuid.uuid4()).replace("-", "")[:28]
    dest_path = os.path.join(_DRIVE_STORE, f"{drive_file_id}_{filename}")

    if os.path.exists(local_video_path):
        shutil.copy2(local_video_path, dest_path)
    else:
        # Fallback: create empty placeholder if source missing
        with open(dest_path, "wb") as f:
            f.write(b"mock_video_placeholder")

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "root")
    web_view_link = f"ENDPOINT_PLACEHOLDER"
    web_content_link = f"ENDPOINT_PLACEHOLDER"

    return json.dumps({
        "id": drive_file_id,
        "name": filename,
        "mimeType": "video/mp4",
        "parents": [folder_id],
        "webViewLink": web_view_link,
        "webContentLink": web_content_link,
        "size": str(os.path.getsize(dest_path)),
        "local_path": dest_path,
        "uploaded_at": int(time.time()),
        "mock": True,
    })


@log_mcp_call(operation_type="tool")
def set_sharing_permissions(file_id: str) -> str:
    """Set Google Drive file sharing to 'anyone with link can view' (mock).

    Simulates the Drive Files.permissions.create API call.
    """
    permission_id = str(uuid.uuid4()).replace("-", "")[:20]
    sharing_url = f"ENDPOINT_PLACEHOLDER"

    return json.dumps({
        "id": permission_id,
        "file_id": file_id,
        "kind": "drive#permission",
        "type": "anyone",
        "role": "reader",
        "sharing_url": sharing_url,
        "status": "mock_set",
        "set_at": int(time.time()),
    })
