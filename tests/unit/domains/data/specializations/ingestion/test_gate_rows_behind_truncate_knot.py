"""Tests for :class:`GateRowsBehindTruncateKnot`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specializations.ingestion.gate_rows_behind_truncate_knot import (
    GateRowsBehindTruncateKnot,
)


class TestGateRowsBehindTruncateKnotConstruction(unittest.TestCase):
    def _make_knot(self) -> GateRowsBehindTruncateKnot:
        rows_knot = MagicMock()
        gate_knot = MagicMock()
        return GateRowsBehindTruncateKnot(
            rows=rows_knot,
            gate=gate_knot,
            _config=KnotConfig(id="gate_rows"),
        )

    def test_construction_succeeds(self) -> None:
        knot = self._make_knot()
        self.assertIsInstance(knot, GateRowsBehindTruncateKnot)


class TestGateRowsBehindTruncateKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_rows_unchanged(self) -> None:
        rows_knot = MagicMock()
        gate_knot = MagicMock()
        knot = GateRowsBehindTruncateKnot(
            rows=rows_knot,
            gate=gate_knot,
            _config=KnotConfig(id="gate_rows"),
        )
        rows_value = [{"id": 1}, {"id": 2}]
        result = await knot.process(rows=rows_value, gate="done", **{})
        self.assertEqual(result, rows_value)

    async def test_process_passes_through_none(self) -> None:
        rows_knot = MagicMock()
        gate_knot = MagicMock()
        knot = GateRowsBehindTruncateKnot(
            rows=rows_knot,
            gate=gate_knot,
            _config=KnotConfig(id="gate_rows"),
        )
        result = await knot.process(rows=None, gate="ok", **{})
        self.assertIsNone(result)

    async def test_process_ignores_gate_value(self) -> None:
        rows_knot = MagicMock()
        gate_knot = MagicMock()
        knot = GateRowsBehindTruncateKnot(
            rows=rows_knot,
            gate=gate_knot,
            _config=KnotConfig(id="gate_rows"),
        )
        sentinel = object()
        result = await knot.process(rows=sentinel, gate=None, **{})
        self.assertIs(result, sentinel)
