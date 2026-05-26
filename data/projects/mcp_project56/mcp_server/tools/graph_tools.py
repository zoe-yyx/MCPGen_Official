"""Graph tools - Mock InfraNodus GraphRAG operations.

Corresponds to n8n nodes:
- InfraNodus Save to Graph: save text to a local JSON-based graph store
- Knowledge Base GraphRAG: query the local graph store with keyword matching
"""

import json
import os
from pathlib import Path
from datetime import datetime

from .utils.log_decorator import log_mcp_call


def _load_graph_store(store_path: str) -> dict:
    """Load graph store from JSON file."""
    if os.path.exists(store_path):
        with open(store_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"graphs": {}}


def _save_graph_store(store_path: str, store: dict) -> None:
    """Save graph store to JSON file."""
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


@log_mcp_call("tool", "save_to_graph")
def save_to_graph(
    graph_name: str,
    text: str,
    category: str,
    store_path: str,
) -> dict[str, str]:
    """Save text content to a local graph store (mock InfraNodus Save to Graph).

    Args:
        graph_name: Name of the graph to save to.
        text: Text content to save.
        category: Category label (e.g., filename).
        store_path: Path to the graph store JSON file.

    Returns:
        Status dict with graph name, category, and text length.
    """
    store = _load_graph_store(store_path)

    if graph_name not in store["graphs"]:
        store["graphs"][graph_name] = {"statements": [], "summary": ""}

    store["graphs"][graph_name]["statements"].append({
        "text": text,
        "category": category,
        "timestamp": datetime.now().isoformat(),
    })

    # Build a simple summary from all statements
    all_texts = [s["text"] for s in store["graphs"][graph_name]["statements"]]
    combined = " ".join(all_texts)
    words = combined.split()
    # Simple keyword extraction: top frequent words (>4 chars)
    word_freq: dict[str, int] = {}
    for w in words:
        w_clean = w.lower().strip(".,!?;:()[]{}\"'")
        if len(w_clean) > 4:
            word_freq[w_clean] = word_freq.get(w_clean, 0) + 1
    top_keywords = sorted(word_freq, key=word_freq.get, reverse=True)[:10]
    store["graphs"][graph_name]["summary"] = (
        f"Graph '{graph_name}' contains {len(store['graphs'][graph_name]['statements'])} documents. "
        f"Key topics: {', '.join(top_keywords)}."
    )

    _save_graph_store(store_path, store)

    return {
        "status": "saved",
        "graph_name": graph_name,
        "category": category,
        "text_length": str(len(text)),
    }


@log_mcp_call("tool", "query_knowledge_base")
def query_knowledge_base(
    graph_name: str,
    prompt: str,
    store_path: str,
) -> dict[str, str | list[str]]:
    """Query the local graph knowledge base (mock InfraNodus GraphRAG).

    Performs keyword-based retrieval over stored statements.

    Args:
        graph_name: Name of the graph to query.
        prompt: User query string.
        store_path: Path to the graph store JSON file.

    Returns:
        Dict with 'summary', 'relevant_statements', and 'topics'.
    """
    store = _load_graph_store(store_path)

    if graph_name not in store["graphs"]:
        return {
            "summary": f"Graph '{graph_name}' not found.",
            "relevant_statements": [],
            "topics": [],
        }

    graph = store["graphs"][graph_name]
    import re
    query_words = set(re.findall(r'\w+', prompt.lower()))

    # Score each statement by keyword overlap
    scored: list[tuple[float, str]] = []
    for statement in graph["statements"]:
        text = statement["text"]
        text_words = set(re.findall(r'\w+', text.lower()))
        overlap = len(query_words & text_words)
        if overlap > 0:
            scored.append((overlap, text))

    scored.sort(key=lambda x: x[0], reverse=True)
    relevant = [text for _, text in scored[:5]]

    return {
        "summary": graph.get("summary", ""),
        "relevant_statements": relevant,
        "topics": graph.get("summary", "").split("Key topics: ")[-1].rstrip(".").split(", ") if "Key topics:" in graph.get("summary", "") else [],
    }
