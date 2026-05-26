"""File tools - Mock Google Drive operations and file extraction.

Corresponds to n8n nodes:
- Search Google Drive: list files from local folder
- Retrieve File: read file content from local folder
- Switch: detect file MIME type
- Extract from PDF / Text / Markdown: extract text content
- Map PDF to Text: normalize extracted content
"""

import os
import mimetypes
from pathlib import Path

from PyPDF2 import PdfReader

from .utils.log_decorator import log_mcp_call


@log_mcp_call("tool", "search_local_files")
def search_local_files(folder_path: str) -> list[dict[str, str]]:
    """Search for files in a local folder (mock Google Drive Search).

    Args:
        folder_path: Path to the local folder containing documents.

    Returns:
        List of file metadata dicts with 'id', 'name', and 'mimeType'.
    """
    files = []
    folder = Path(folder_path)
    if not folder.exists():
        return files

    for file_path in sorted(folder.iterdir()):
        if file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            files.append({
                "id": str(file_path),
                "name": file_path.name,
                "mimeType": mime_type or "application/octet-stream",
            })
    return files


@log_mcp_call("tool", "retrieve_file")
def retrieve_file(file_path: str) -> dict[str, str]:
    """Retrieve a file's binary info (mock Google Drive Download).

    Args:
        file_path: Absolute or relative path to the file.

    Returns:
        Dict with 'path', 'name', and 'mimeType'.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    mime_type, _ = mimetypes.guess_type(str(p))
    return {
        "path": str(p),
        "name": p.name,
        "mimeType": mime_type or "application/octet-stream",
    }


@log_mcp_call("tool", "detect_file_type")
def detect_file_type(mime_type: str) -> str:
    """Detect file category based on MIME type (mock Switch node).

    Args:
        mime_type: The MIME type string of the file.

    Returns:
        File category: 'pdf', 'text', 'markdown', 'json', 'csv', or 'unknown'.
    """
    type_map = {
        "application/pdf": "pdf",
        "text/plain": "text",
        "text/markdown": "markdown",
        "application/json": "json",
        "text/csv": "csv",
    }
    return type_map.get(mime_type, "unknown")


@log_mcp_call("tool", "extract_pdf_text")
def extract_pdf_text(file_path: str) -> str:
    """Extract text content from a PDF file.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Extracted text content.
    """
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts)


@log_mcp_call("tool", "extract_text_file")
def extract_text_file(file_path: str) -> str:
    """Extract text content from a plain text file.

    Args:
        file_path: Path to the text file.

    Returns:
        File text content.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@log_mcp_call("tool", "extract_markdown_file")
def extract_markdown_file(file_path: str) -> str:
    """Extract text content from a Markdown file.

    Args:
        file_path: Path to the Markdown file.

    Returns:
        File text content.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@log_mcp_call("tool", "map_to_text")
def map_to_text(raw_text: str) -> str:
    """Normalize extracted text (mock Map PDF to Text node).

    Args:
        raw_text: Raw extracted text from any file type.

    Returns:
        Cleaned text with normalized whitespace.
    """
    lines = raw_text.strip().splitlines()
    cleaned = "\n".join(line.strip() for line in lines if line.strip())
    return cleaned
