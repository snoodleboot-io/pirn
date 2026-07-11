"""Tests for the lazy grammar backend (F20-S3)."""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

from pirn_agents.specializations.structured_output import _grammar_backend


class TestGrammarBackend(unittest.TestCase):
    def test_missing_backend_raises_friendly_error(self) -> None:
        # CI installs the ``grammar`` extra, so absence must be simulated.
        with mock.patch.dict(sys.modules, {"outlines": None}):
            with self.assertRaises(ImportError) as ctx:
                _grammar_backend.compile_constraint({"json_schema": {"type": "object"}})

        assert 'pip install "pirn-agents[grammar]"' in str(ctx.exception)

    def test_present_backend_returns_compiled_record(self) -> None:
        fake_outlines = types.ModuleType("outlines")
        constraint = {"json_schema": {"type": "object"}, "regex": "^a$"}

        with mock.patch.dict(sys.modules, {"outlines": fake_outlines}):
            record = _grammar_backend.compile_constraint(constraint)

        assert record["backend"] == "outlines"
        assert record["constraint"] == constraint


if __name__ == "__main__":
    unittest.main()
