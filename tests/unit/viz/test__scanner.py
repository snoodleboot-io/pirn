"""Tests for TapestryGraphScanner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.viz._scanner import TapestryGraphScanner


class TestTapestryGraphScannerDurationMs(unittest.TestCase):
    def test_valid_iso_timestamps(self) -> None:
        start = "2026-01-01T10:00:00"
        end = "2026-01-01T10:00:01"
        ms = TapestryGraphScanner._duration_ms(start, end)
        self.assertEqual(ms, 1000)

    def test_invalid_returns_zero(self) -> None:
        ms = TapestryGraphScanner._duration_ms("bad", "bad")
        self.assertEqual(ms, 0)

    def test_none_returns_zero(self) -> None:
        ms = TapestryGraphScanner._duration_ms(None, None)
        self.assertEqual(ms, 0)

    def test_negative_clamped_to_zero(self) -> None:
        start = "2026-01-01T10:00:01"
        end = "2026-01-01T10:00:00"
        ms = TapestryGraphScanner._duration_ms(start, end)
        self.assertEqual(ms, 0)


class TestTapestryGraphScannerIsIgnored(unittest.TestCase):
    def test_pycache_ignored(self) -> None:
        p = Path("/project/__pycache__/file.py")
        self.assertTrue(TapestryGraphScanner._is_ignored(p))

    def test_git_ignored(self) -> None:
        p = Path("/project/.git/config")
        self.assertTrue(TapestryGraphScanner._is_ignored(p))

    def test_normal_path_not_ignored(self) -> None:
        p = Path("/project/src/pipeline.py")
        self.assertFalse(TapestryGraphScanner._is_ignored(p))

    def test_venv_ignored(self) -> None:
        p = Path("/project/.venv/lib/something.py")
        self.assertTrue(TapestryGraphScanner._is_ignored(p))


class TestTapestryGraphScannerParseIso(unittest.TestCase):
    def test_basic_iso(self) -> None:
        dt = TapestryGraphScanner._parse_iso("2026-01-15T12:30:00")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 15)

    def test_with_z_suffix(self) -> None:
        dt = TapestryGraphScanner._parse_iso("2026-01-15T12:30:00Z")
        self.assertEqual(dt.year, 2026)

    def test_with_plus00_suffix(self) -> None:
        dt = TapestryGraphScanner._parse_iso("2026-01-15T12:30:00+00:00")
        self.assertEqual(dt.year, 2026)

    def test_space_separator(self) -> None:
        dt = TapestryGraphScanner._parse_iso("2026-01-15 12:30:00")
        self.assertEqual(dt.hour, 12)


class TestTapestryGraphScannerKnotDescription(unittest.TestCase):
    def test_docstring_first_line(self) -> None:
        class MyKnot:
            """This is my knot.

            More details here.
            """

        knot = MyKnot()
        result = TapestryGraphScanner._knot_description(knot)
        self.assertEqual(result, "This is my knot.")

    def test_no_docstring_returns_empty(self) -> None:
        class NoDoc:
            pass

        NoDoc.__doc__ = None
        result = TapestryGraphScanner._knot_description(NoDoc())
        self.assertEqual(result, "")


class TestTapestryGraphScannerScanFolder(unittest.TestCase):
    def test_empty_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scanner = TapestryGraphScanner()
            tapestries, runs = scanner.scan_folder(Path(tmp))
        self.assertEqual(tapestries, [])
        self.assertEqual(runs, [])

    def test_non_pipeline_yaml_produces_error_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            yaml_file = Path(tmp) / "pipeline.yaml"
            yaml_file.write_text("key: value\n")
            scanner = TapestryGraphScanner()
            tapestries, runs = scanner.scan_folder(Path(tmp))
        # The loader will fail on a non-pipeline YAML; scanner returns error graphs.
        self.assertEqual(len(tapestries), 1)
        self.assertIsNotNone(tapestries[0].error)
