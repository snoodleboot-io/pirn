"""Tests for :class:`ExactDeduplicator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.deduplication.exact_deduplicator import (
    ExactDeduplicator,
)
from pirn.tapestry import Tapestry


def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(key_columns, tiebreaker_column, tiebreaker_direction="desc"):
    with Tapestry():
        knot = ExactDeduplicator(
            rows=_rows_param(),
            key_columns=key_columns,
            tiebreaker_column=tiebreaker_column,
            tiebreaker_direction=tiebreaker_direction,
            _config=KnotConfig(id="dedup"),
        )
    return knot


class TestConstruction:
    def test_rejects_invalid_key_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            with Tapestry():
                ExactDeduplicator(
                    rows=_rows_param(),
                    key_columns=["bad col"],
                    tiebreaker_column="score",
                    _config=KnotConfig(id="x"),
                )

    def test_rejects_invalid_tiebreaker(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            with Tapestry():
                ExactDeduplicator(
                    rows=_rows_param(),
                    key_columns=["id"],
                    tiebreaker_column="bad col",
                    _config=KnotConfig(id="x"),
                )

    def test_rejects_invalid_direction(self) -> None:
        with pytest.raises(ValueError, match="tiebreaker_direction"):
            with Tapestry():
                ExactDeduplicator(
                    rows=_rows_param(),
                    key_columns=["id"],
                    tiebreaker_column="score",
                    tiebreaker_direction="up",  # type: ignore[arg-type]
                    _config=KnotConfig(id="x"),
                )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_no_duplicates_returns_all(self) -> None:
        rows = [{"id": 1, "score": 10}, {"id": 2, "score": 20}]
        knot = _make(key_columns=["id"], tiebreaker_column="score")
        result = await knot.process(rows=rows)
        assert len(result) == 2

    async def test_keeps_highest_score_on_desc(self) -> None:
        rows = [
            {"id": 1, "score": 5},
            {"id": 1, "score": 9},
            {"id": 2, "score": 3},
        ]
        knot = _make(key_columns=["id"], tiebreaker_column="score", tiebreaker_direction="desc")
        result = await knot.process(rows=rows)
        id1 = next(r for r in result if r["id"] == 1)
        assert id1["score"] == 9

    async def test_keeps_lowest_score_on_asc(self) -> None:
        rows = [
            {"id": 1, "score": 5},
            {"id": 1, "score": 9},
        ]
        knot = _make(key_columns=["id"], tiebreaker_column="score", tiebreaker_direction="asc")
        result = await knot.process(rows=rows)
        assert result[0]["score"] == 5

    async def test_composite_key(self) -> None:
        rows = [
            {"a": 1, "b": 2, "v": 1},
            {"a": 1, "b": 2, "v": 2},
            {"a": 1, "b": 3, "v": 1},
        ]
        knot = _make(key_columns=["a", "b"], tiebreaker_column="v")
        result = await knot.process(rows=rows)
        assert len(result) == 2

    async def test_empty_input(self) -> None:
        knot = _make(key_columns=["id"], tiebreaker_column="score")
        result = await knot.process(rows=[])
        assert result == []
