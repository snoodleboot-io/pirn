"""Tests for check._loader._load_factory."""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch


class TestLoadFactory(unittest.TestCase):
    def _call(self, spec: str):
        from pirn.check._loader import _load_factory
        return _load_factory(spec)

    def test_valid_spec_returns_callable(self) -> None:
        # Use a real importable symbol.
        result = self._call("pathlib:Path")
        import pathlib
        self.assertIs(result, pathlib.Path)

    def test_missing_colon_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            self._call("no_colon_here")
        self.assertEqual(cm.exception.code, 2)

    def test_nonexistent_module_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            self._call("pirn._nonexistent_module_xyz:fn")
        self.assertEqual(cm.exception.code, 2)

    def test_missing_attribute_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            self._call("pathlib:_does_not_exist_123")
        self.assertEqual(cm.exception.code, 2)

    def test_function_attribute_returned(self) -> None:
        import os.path
        result = self._call("os.path:join")
        self.assertIs(result, os.path.join)
