"""Tests for :class:`SessionizationKnot`."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.timeseries.sessionization_knot import (
    SessionizationKnot,
)
from pirn.tapestry import Tapestry


def _ts(minutes: float) -> datetime:
    return datetime(2024, 1, 1) + timedelta(minutes=minutes)


def _make_knot(**overrides: Any) -> SessionizationKnot:
    defaults: dict[str, Any] = {
        "rows": [],
        "entity_columns": ["uid"],
        "timestamp_column": "ts",
        "inactivity_minutes": 30,
        "_config": KnotConfig(id="session"),
    }
    defaults.update(overrides)
    return SessionizationKnot(**defaults)


class TestSessionizationKnot(unittest.IsolatedAsyncioTestCase):
    async def test_single_session(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u1", "ts": _ts(5)},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = SessionizationKnot(
                rows=r_knot,
                entity_columns=["uid"],
                timestamp_column="ts",
                inactivity_minutes=30,
                _config=KnotConfig(id="session"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out[0]["session_id"] == out[1]["session_id"]
        assert out[0]["session_seq"] == 1
        assert out[1]["session_seq"] == 2

    async def test_gap_creates_new_session(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u1", "ts": _ts(60)},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows2"))
            k = SessionizationKnot(
                rows=r_knot,
                entity_columns=["uid"],
                timestamp_column="ts",
                inactivity_minutes=30,
                _config=KnotConfig(id="session2"),
            )
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out[0]["session_id"] != out[1]["session_id"]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u2", "ts": _ts(1)},
        ]

        @knot
        async def emit_rows() -> list:
            return rows

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            SessionizationKnot(
                rows=r_knot,
                entity_columns=["uid"],
                timestamp_column="ts",
                inactivity_minutes=30,
                _config=KnotConfig(id="session-wire"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["session-wire"]
        assert out[0]["session_id"] != out[1]["session_id"]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> SessionizationKnot:
        defaults: dict[str, Any] = {
            "rows": [],
            "entity_columns": ["uid"],
            "timestamp_column": "ts",
            "inactivity_minutes": 30,
        }
        defaults.update(kwargs)
        with Tapestry():
            return SessionizationKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: SessionizationKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "entity_columns": ["uid"],
            "timestamp_column": "ts",
            "inactivity_minutes": 30,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_positive_gap(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "inactivity_minutes"):
            await self._call(k, inactivity_minutes=-1)

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, entity_columns=["bad col"])

    async def test_session_seq_resets_on_new_session(self) -> None:
        k = self._make_knot()
        rows = [
            {"uid": "u1", "ts": _ts(0)},
            {"uid": "u1", "ts": _ts(60)},
        ]
        result = await k.process(
            rows=rows, entity_columns=["uid"],
            timestamp_column="ts", inactivity_minutes=30,
        )
        assert result[1]["session_seq"] == 1

    async def test_empty_input_returns_empty(self) -> None:
        k = self._make_knot()
        result = await k.process(
            rows=[], entity_columns=["uid"],
            timestamp_column="ts", inactivity_minutes=30,
        )
        assert result == []
