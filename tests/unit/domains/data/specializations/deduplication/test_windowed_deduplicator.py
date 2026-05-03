"""Tests for :class:`WindowedDeduplicator`."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.deduplication.windowed_deduplicator import (
    WindowedDeduplicator,
)
from pirn.tapestry import Tapestry


def _ts(offset_minutes: float) -> datetime:
    return datetime(2024, 1, 1, 0, 0, 0) + timedelta(minutes=offset_minutes)


def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = WindowedDeduplicator(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="wdedup"),
        )
    return knot


class TestConstruction:
    def test_rejects_non_positive_window(self) -> None:
        with pytest.raises(ValueError, match="window_minutes"):
            _make(key_columns=["id"], timestamp_column="ts", window_minutes=0)

    def test_rejects_invalid_key(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(key_columns=["bad col"], timestamp_column="ts", window_minutes=5)


@pytest.mark.asyncio
class TestBehaviour:
    async def test_same_key_within_window_deduped(self) -> None:
        rows = [
            {"id": "A", "ts": _ts(0)},
            {"id": "A", "ts": _ts(2)},
        ]
        knot = _make(key_columns=["id"], timestamp_column="ts", window_minutes=5)
        result = await knot.process(rows=rows)
        assert len(result) == 1
        assert result[0]["ts"] == _ts(0)

    async def test_same_key_after_window_new_event(self) -> None:
        rows = [
            {"id": "A", "ts": _ts(0)},
            {"id": "A", "ts": _ts(10)},
        ]
        knot = _make(key_columns=["id"], timestamp_column="ts", window_minutes=5)
        result = await knot.process(rows=rows)
        assert len(result) == 2

    async def test_different_keys_both_kept(self) -> None:
        rows = [
            {"id": "A", "ts": _ts(0)},
            {"id": "B", "ts": _ts(1)},
        ]
        knot = _make(key_columns=["id"], timestamp_column="ts", window_minutes=5)
        result = await knot.process(rows=rows)
        assert len(result) == 2

    async def test_iso_string_timestamp(self) -> None:
        rows = [
            {"id": "A", "ts": "2024-01-01T00:00:00"},
            {"id": "A", "ts": "2024-01-01T00:03:00"},
        ]
        knot = _make(key_columns=["id"], timestamp_column="ts", window_minutes=5)
        result = await knot.process(rows=rows)
        assert len(result) == 1

    async def test_empty_input(self) -> None:
        knot = _make(key_columns=["id"], timestamp_column="ts", window_minutes=5)
        result = await knot.process(rows=[])
        assert result == []
