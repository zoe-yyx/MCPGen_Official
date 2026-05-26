"""Unit tests for tool functions - tests without MCP, direct Python calls."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from mcp_server.tools.file_tools import (
    search_local_files,
    retrieve_file,
    detect_file_type,
    extract_text_file,
    extract_markdown_file,
    map_to_text,
)
from mcp_server.tools.graph_tools import save_to_graph, query_knowledge_base


class TestFileTools(unittest.TestCase):
    """Tests for file-related tool functions."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create test files
        self.txt_path = os.path.join(self.test_dir, "test.txt")
        with open(self.txt_path, "w", encoding="utf-8") as f:
            f.write("Hello world. This is a test document about GraphRAG.")

        self.md_path = os.path.join(self.test_dir, "test.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write("# Test\n\nThis is a markdown document about knowledge graphs.")

    def test_search_local_files(self):
        files = search_local_files(self.test_dir)
        self.assertEqual(len(files), 2)
        names = {f["name"] for f in files}
        self.assertIn("test.txt", names)
        self.assertIn("test.md", names)

    def test_search_nonexistent_folder(self):
        files = search_local_files("/nonexistent/folder")
        self.assertEqual(files, [])

    def test_retrieve_file(self):
        result = retrieve_file(self.txt_path)
        self.assertEqual(result["name"], "test.txt")
        self.assertEqual(result["mimeType"], "text/plain")

    def test_retrieve_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            retrieve_file("/nonexistent/file.txt")

    def test_detect_file_type(self):
        self.assertEqual(detect_file_type("application/pdf"), "pdf")
        self.assertEqual(detect_file_type("text/plain"), "text")
        self.assertEqual(detect_file_type("text/markdown"), "markdown")
        self.assertEqual(detect_file_type("application/json"), "json")
        self.assertEqual(detect_file_type("text/csv"), "csv")
        self.assertEqual(detect_file_type("application/octet-stream"), "unknown")

    def test_extract_text_file(self):
        text = extract_text_file(self.txt_path)
        self.assertIn("Hello world", text)
        self.assertIn("GraphRAG", text)

    def test_extract_markdown_file(self):
        text = extract_markdown_file(self.md_path)
        self.assertIn("# Test", text)
        self.assertIn("knowledge graphs", text)

    def test_map_to_text(self):
        raw = "  Hello world  \n\n  This is a test  \n  "
        cleaned = map_to_text(raw)
        self.assertEqual(cleaned, "Hello world\nThis is a test")


class TestGraphTools(unittest.TestCase):
    """Tests for graph-related tool functions."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.test_dir, "test_graph.json")

    def test_save_to_graph(self):
        result = save_to_graph(
            graph_name="test_graph",
            text="GraphRAG combines knowledge graphs with retrieval augmented generation.",
            category="filename: test.txt",
            store_path=self.store_path,
        )
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["graph_name"], "test_graph")
        # Verify file was created
        self.assertTrue(os.path.exists(self.store_path))

    def test_query_knowledge_base_found(self):
        # First save some data
        save_to_graph(
            graph_name="test_graph",
            text="GraphRAG combines knowledge graphs with retrieval augmented generation for better results.",
            category="filename: doc1.txt",
            store_path=self.store_path,
        )
        save_to_graph(
            graph_name="test_graph",
            text="Knowledge graphs represent entities and relationships in a structured way.",
            category="filename: doc2.txt",
            store_path=self.store_path,
        )

        result = query_knowledge_base(
            graph_name="test_graph",
            prompt="What is GraphRAG?",
            store_path=self.store_path,
        )
        self.assertIn("summary", result)
        self.assertIsInstance(result["relevant_statements"], list)
        self.assertGreater(len(result["relevant_statements"]), 0)

    def test_query_knowledge_base_not_found(self):
        result = query_knowledge_base(
            graph_name="nonexistent",
            prompt="test",
            store_path=self.store_path,
        )
        self.assertIn("not found", result["summary"])

    def test_multiple_saves_accumulate(self):
        save_to_graph("g", "Text one about graphs.", "cat1", self.store_path)
        save_to_graph("g", "Text two about retrieval.", "cat2", self.store_path)

        with open(self.store_path, "r", encoding="utf-8") as f:
            store = json.load(f)
        self.assertEqual(len(store["graphs"]["g"]["statements"]), 2)


if __name__ == "__main__":
    unittest.main()
