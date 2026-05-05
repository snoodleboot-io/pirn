"""Tests for ExploreCli."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pirn.viz._explore_cli import ExploreCli, main


class TestExploreCli(unittest.TestCase):
    def test_nonexistent_folder_returns_1(self) -> None:
        cli = ExploreCli()
        result = cli.run(["/nonexistent/path/xyz"])
        self.assertEqual(result, 1)

    def test_valid_folder_no_open_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pirn.viz.explorer.generate_explorer_html", return_value="<html/>"):
                result = ExploreCli().run([tmp, "--no-open"])
        self.assertEqual(result, 0)

    def test_output_file_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "out.html")
            with patch("pirn.viz.explorer.generate_explorer_html", return_value="<html>hi</html>"):
                ExploreCli().run([tmp, "--output", out, "--no-open"])
            self.assertTrue(Path(out).exists())
            self.assertEqual(Path(out).read_text(encoding="utf-8"), "<html>hi</html>")

    def test_default_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pirn.viz.explorer.generate_explorer_html", return_value="<html/>"):
                ExploreCli().run([tmp, "--no-open"])
            default_out = Path(tmp) / "pirn_explorer.html"
            self.assertTrue(default_out.exists())

    def test_main_wrapper_callable(self) -> None:
        self.assertTrue(callable(main))

    def test_main_delegates_to_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("pirn.viz.explorer.generate_explorer_html", return_value="<html/>"):
                code = main([tmp, "--no-open"])
        self.assertEqual(code, 0)
