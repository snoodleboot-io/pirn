"""Tests for ExplorerHtmlGenerator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pirn.viz._tapestry_graph import TapestryGraph
from pirn.viz.explorer import ExplorerHtmlGenerator, generate_explorer_html


class TestExplorerHtmlGeneratorGenerate(unittest.TestCase):
    def test_empty_folder_produces_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = ExplorerHtmlGenerator.generate(tmp)
        self.assertIn("<!DOCTYPE html", html)

    def test_contains_explorer_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = ExplorerHtmlGenerator.generate(tmp)
        self.assertIn("pirn explorer", html)

    def test_data_placeholder_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = ExplorerHtmlGenerator.generate(tmp)
        self.assertNotIn("__EXPLORER_DATA__", html)

    def test_tapestry_data_injected(self) -> None:
        graphs = [TapestryGraph(name="my_pipe", source="pipe.yaml")]
        with patch("pirn.viz._scanner.scan_folder", return_value=(graphs, [])):
            with tempfile.TemporaryDirectory() as tmp:
                html = ExplorerHtmlGenerator.generate(tmp)
        self.assertIn("my_pipe", html)

    def test_folder_string_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = generate_explorer_html(tmp)
        self.assertIn("<!DOCTYPE html", html)

    def test_folder_path_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = generate_explorer_html(Path(tmp))
        self.assertIn("<!DOCTYPE html", html)
