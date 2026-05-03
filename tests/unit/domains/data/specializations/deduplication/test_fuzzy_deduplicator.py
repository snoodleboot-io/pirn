"""Tests for :class:`FuzzyDeduplicator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.deduplication.fuzzy_deduplicator import (
    FuzzyDeduplicator,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = FuzzyDeduplicator(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="fuzzy"),
        )
    return knot


class TestConstruction:
    def test_rejects_invalid_match_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(match_column="bad col")

    def test_rejects_invalid_metric(self) -> None:
        with pytest.raises(ValueError, match="similarity_metric"):
            _make(match_column="name", similarity_metric="hamming")

    def test_rejects_threshold_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            _make(match_column="name", threshold=1.1)

    def test_rejects_zero_blocking_length(self) -> None:
        with pytest.raises(ValueError, match="blocking_key_length"):
            _make(match_column="name", blocking_key_length=0)


@pytest.mark.asyncio
class TestBehaviour:
    async def test_exact_duplicates_merged(self) -> None:
        rows = [{"name": "alice"}, {"name": "alice"}]
        knot = _make(match_column="name", threshold=0.9)
        result = await knot.process(rows=rows)
        assert len(result) == 1

    async def test_near_duplicate_merged_levenshtein(self) -> None:
        rows = [{"name": "alice"}, {"name": "alic3"}]
        knot = _make(match_column="name", similarity_metric="levenshtein", threshold=0.7)
        result = await knot.process(rows=rows)
        assert len(result) == 1

    async def test_distinct_names_not_merged(self) -> None:
        rows = [{"name": "alice"}, {"name": "bob"}]
        knot = _make(match_column="name", threshold=0.9)
        result = await knot.process(rows=rows)
        assert len(result) == 2

    async def test_jaro_winkler_near_duplicate(self) -> None:
        rows = [{"name": "jennifer"}, {"name": "jenifer"}]
        knot = _make(match_column="name", similarity_metric="jaro_winkler", threshold=0.90)
        result = await knot.process(rows=rows)
        assert len(result) == 1

    async def test_empty_input(self) -> None:
        knot = _make(match_column="name")
        result = await knot.process(rows=[])
        assert result == []
