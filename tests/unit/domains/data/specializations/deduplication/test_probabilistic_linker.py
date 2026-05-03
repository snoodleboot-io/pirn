"""Tests for :class:`ProbabilisticLinker`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.deduplication.probabilistic_linker import (
    ProbabilisticLinker,
)
from pirn.tapestry import Tapestry



def _left_param():
    return Parameter("left_rows", list, _config=KnotConfig(id="left_rows"))


def _right_param():
    return Parameter("right_rows", list, _config=KnotConfig(id="right_rows"))


def _make(field_specs, match_threshold=3.0, review_threshold=0.0):
    with Tapestry():
        knot = ProbabilisticLinker(
            left_rows=_left_param(),
            right_rows=_right_param(),
            field_specs=field_specs,
            match_threshold=match_threshold,
            review_threshold=review_threshold,
            _config=KnotConfig(id="linker"),
        )
    return knot


_SPECS = [
    {"column": "name", "m": 0.9, "u": 0.1},
    {"column": "dob", "m": 0.95, "u": 0.01},
]


class TestConstruction:
    def test_rejects_invalid_column_name(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make([{"column": "bad col", "m": 0.9, "u": 0.1}])

    def test_rejects_out_of_range_m(self) -> None:
        with pytest.raises(ValueError, match=r"'m'"):
            _make([{"column": "name", "m": 1.5, "u": 0.1}])

    def test_rejects_thresholds_inverted(self) -> None:
        with pytest.raises(ValueError, match="match_threshold"):
            _make(_SPECS, match_threshold=0.0, review_threshold=5.0)


@pytest.mark.asyncio
class TestBehaviour:
    async def test_identical_records_classified_as_match(self) -> None:
        left = [{"name": "Alice", "dob": "1990-01-01"}]
        right = [{"name": "Alice", "dob": "1990-01-01"}]
        knot = _make(_SPECS)
        result = await knot.process(left_rows=left, right_rows=right)
        assert result[0]["classification"] == "match"

    async def test_no_matching_fields_non_match(self) -> None:
        left = [{"name": "Alice", "dob": "1990-01-01"}]
        right = [{"name": "Bob", "dob": "1985-06-15"}]
        knot = _make(_SPECS, match_threshold=3.0, review_threshold=0.0)
        result = await knot.process(left_rows=left, right_rows=right)
        assert result[0]["classification"] == "non_match"

    async def test_partial_match_review(self) -> None:
        left = [{"name": "Alice", "dob": "1990-01-01"}]
        right = [{"name": "Alice", "dob": "1985-06-15"}]
        specs = [
            {"column": "name", "m": 0.9, "u": 0.1},
        ]
        knot = _make(specs, match_threshold=5.0, review_threshold=0.0)
        result = await knot.process(left_rows=left, right_rows=right)
        assert result[0]["classification"] == "review"

    async def test_cross_product_size(self) -> None:
        left = [{"name": "A", "dob": "x"}, {"name": "B", "dob": "y"}]
        right = [{"name": "A", "dob": "x"}, {"name": "C", "dob": "z"}]
        knot = _make(_SPECS)
        result = await knot.process(left_rows=left, right_rows=right)
        assert len(result) == 4

    async def test_weight_and_indices_present(self) -> None:
        left = [{"name": "Alice", "dob": "1990"}]
        right = [{"name": "Alice", "dob": "1990"}]
        knot = _make(_SPECS)
        result = await knot.process(left_rows=left, right_rows=right)
        assert "weight" in result[0]
        assert result[0]["left_index"] == 0
        assert result[0]["right_index"] == 0
