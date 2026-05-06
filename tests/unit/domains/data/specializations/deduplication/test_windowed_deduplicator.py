"""Tests for :class:`WindowedDeduplicator`."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.deduplication.windowed_deduplicator import (
    WindowedDeduplicator,
)
from pirn.tapestry import Tapestry

_KEY_COLUMNS = ("id",)
_TIMESTAMP_COLUMN = "ts"
_WINDOW_MINUTES = 5.0


def _ts(offset_minutes: float) -> datetime:
    return datetime(2024, 1, 1, 0, 0, 0) + timedelta(minutes=offset_minutes)


def _rows_param() -> Parameter:
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make_knot(**kwargs: Any) -> WindowedDeduplicator:
    defaults: dict[str, Any] = {
        "key_columns": _KEY_COLUMNS,
        "timestamp_column": _TIMESTAMP_COLUMN,
        "window_minutes": _WINDOW_MINUTES,
    }
    defaults.update(kwargs)
    return WindowedDeduplicator(
        rows=_rows_param(),
        **defaults,
        _config=KnotConfig(id="wdedup"),
    )


class TestWindowedDeduplicator(unittest.IsolatedAsyncioTestCase):
    async def test_same_key_within_window_deduped(self) -> None:
        rows = [
            {"id": "A", "ts": _ts(0)},
            {"id": "A", "ts": _ts(2)},
        ]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=rows,
            key_columns=_KEY_COLUMNS,
            timestamp_column=_TIMESTAMP_COLUMN,
            window_minutes=_WINDOW_MINUTES,
        )
        assert len(result) == 1
        assert result[0]["ts"] == _ts(0)

    async def test_same_key_after_window_new_event(self) -> None:
        rows = [
            {"id": "A", "ts": _ts(0)},
            {"id": "A", "ts": _ts(10)},
        ]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=rows,
            key_columns=_KEY_COLUMNS,
            timestamp_column=_TIMESTAMP_COLUMN,
            window_minutes=_WINDOW_MINUTES,
        )
        assert len(result) == 2

    async def test_different_keys_both_kept(self) -> None:
        rows = [
            {"id": "A", "ts": _ts(0)},
            {"id": "B", "ts": _ts(1)},
        ]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=rows,
            key_columns=_KEY_COLUMNS,
            timestamp_column=_TIMESTAMP_COLUMN,
            window_minutes=_WINDOW_MINUTES,
        )
        assert len(result) == 2

    async def test_iso_string_timestamp(self) -> None:
        rows = [
            {"id": "A", "ts": "2024-01-01T00:00:00"},
            {"id": "A", "ts": "2024-01-01T00:03:00"},
        ]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=rows,
            key_columns=_KEY_COLUMNS,
            timestamp_column=_TIMESTAMP_COLUMN,
            window_minutes=_WINDOW_MINUTES,
        )
        assert len(result) == 1

    async def test_empty_input(self) -> None:
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=[],
            key_columns=_KEY_COLUMNS,
            timestamp_column=_TIMESTAMP_COLUMN,
            window_minutes=_WINDOW_MINUTES,
        )
        assert result == []

    async def test_wired_tapestry_run(self) -> None:
        @knot
        async def emit_rows() -> list[dict[str, Any]]:
            return [
                {"id": "A", "ts": _ts(0)},
                {"id": "A", "ts": _ts(2)},
            ]

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = WindowedDeduplicator(
                rows=r_knot,
                key_columns=_KEY_COLUMNS,
                timestamp_column=_TIMESTAMP_COLUMN,
                window_minutes=_WINDOW_MINUTES,
                _config=KnotConfig(id="wdedup"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs[k.config.id]) == 1


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_timestamp_column_from_upstream_knot(self) -> None:
        @knot
        async def emit_col() -> str:
            return _TIMESTAMP_COLUMN

        with Tapestry() as t:
            tc_knot = emit_col(_config=KnotConfig(id="tc"))
            k = WindowedDeduplicator(
                rows=_rows_param(),
                key_columns=_KEY_COLUMNS,
                timestamp_column=tc_knot,
                window_minutes=_WINDOW_MINUTES,
                _config=KnotConfig(id="wdedup"),
            )
        _ = t
        assert k is not None


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> WindowedDeduplicator:
        defaults: dict[str, Any] = {
            "key_columns": _KEY_COLUMNS,
            "timestamp_column": _TIMESTAMP_COLUMN,
            "window_minutes": _WINDOW_MINUTES,
        }
        defaults.update(kwargs)
        with Tapestry():
            return WindowedDeduplicator(
                rows=_rows_param(),
                **defaults,
                _config=KnotConfig(id="val"),
            )

    async def _call(self, k: WindowedDeduplicator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "key_columns": _KEY_COLUMNS,
            "timestamp_column": _TIMESTAMP_COLUMN,
            "window_minutes": _WINDOW_MINUTES,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_positive_window(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "window_minutes"):
            await self._call(k, window_minutes=0)

    async def test_rejects_invalid_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, key_columns=["bad col"])
