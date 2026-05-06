"""Tests for :class:`RowsBehindTruncateCheckKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.ingestion.rows_behind_truncate_check_knot import (
    RowsBehindTruncateCheckKnot,
)
from pirn.tapestry import Tapestry


def _make_knot() -> RowsBehindTruncateCheckKnot:
    return RowsBehindTruncateCheckKnot(
        rows=MagicMock(),
        gate=MagicMock(),
        _config=KnotConfig(id="gate_rows"),
    )


class TestRowsBehindTruncateCheckKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_rows_unchanged(self) -> None:
        k = _make_knot()
        rows_value = [{"id": 1}, {"id": 2}]
        result = await k.process(rows=rows_value, gate="done")
        assert result == rows_value

    async def test_passes_through_none(self) -> None:
        k = _make_knot()
        result = await k.process(rows=None, gate="ok")
        assert result is None

    async def test_ignores_gate_value(self) -> None:
        k = _make_knot()
        sentinel = object()
        result = await k.process(rows=sentinel, gate=None)
        assert result is sentinel


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [{"id": 1}]

        @knot
        async def emit_gate() -> str:
            return "done"

        with Tapestry() as t:
            r = emit_rows(_config=KnotConfig(id="rows"))
            g = emit_gate(_config=KnotConfig(id="gate"))
            k = RowsBehindTruncateCheckKnot(
                rows=r, gate=g, _config=KnotConfig(id="check")
            )
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id] == [{"id": 1}]
