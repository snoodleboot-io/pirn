"""Tests for :class:`ProbabilisticLinker`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.deduplication.probabilistic_linker import (
    ProbabilisticLinker,
)
from pirn.tapestry import Tapestry

_SPECS = [
    {"column": "name", "m": 0.9, "u": 0.1},
    {"column": "dob", "m": 0.95, "u": 0.01},
]
_MATCH_THRESHOLD = 3.0
_REVIEW_THRESHOLD = 0.0


def _left_param() -> Parameter:
    return Parameter("left_rows", list, _config=KnotConfig(id="left_rows"))


def _right_param() -> Parameter:
    return Parameter("right_rows", list, _config=KnotConfig(id="right_rows"))


def _make_knot(**kwargs: Any) -> ProbabilisticLinker:
    defaults: dict[str, Any] = {
        "field_specs": _SPECS,
        "match_threshold": _MATCH_THRESHOLD,
        "review_threshold": _REVIEW_THRESHOLD,
    }
    defaults.update(kwargs)
    return ProbabilisticLinker(
        left_rows=_left_param(),
        right_rows=_right_param(),
        **defaults,
        _config=KnotConfig(id="linker"),
    )


class TestProbabilisticLinker(unittest.IsolatedAsyncioTestCase):
    async def test_identical_records_classified_as_match(self) -> None:
        left = [{"name": "Alice", "dob": "1990-01-01"}]
        right = [{"name": "Alice", "dob": "1990-01-01"}]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            left_rows=left,
            right_rows=right,
            field_specs=_SPECS,
            match_threshold=_MATCH_THRESHOLD,
            review_threshold=_REVIEW_THRESHOLD,
        )
        assert result[0]["classification"] == "match"

    async def test_no_matching_fields_non_match(self) -> None:
        left = [{"name": "Alice", "dob": "1990-01-01"}]
        right = [{"name": "Bob", "dob": "1985-06-15"}]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            left_rows=left,
            right_rows=right,
            field_specs=_SPECS,
            match_threshold=_MATCH_THRESHOLD,
            review_threshold=_REVIEW_THRESHOLD,
        )
        assert result[0]["classification"] == "non_match"

    async def test_partial_match_review(self) -> None:
        left = [{"name": "Alice", "dob": "1990-01-01"}]
        right = [{"name": "Alice", "dob": "1985-06-15"}]
        specs = [{"column": "name", "m": 0.9, "u": 0.1}]
        with Tapestry():
            k = _make_knot(field_specs=specs, match_threshold=5.0, review_threshold=0.0)
        result = await k.process(
            left_rows=left,
            right_rows=right,
            field_specs=specs,
            match_threshold=5.0,
            review_threshold=0.0,
        )
        assert result[0]["classification"] == "review"

    async def test_cross_product_size(self) -> None:
        left = [{"name": "A", "dob": "x"}, {"name": "B", "dob": "y"}]
        right = [{"name": "A", "dob": "x"}, {"name": "C", "dob": "z"}]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            left_rows=left,
            right_rows=right,
            field_specs=_SPECS,
            match_threshold=_MATCH_THRESHOLD,
            review_threshold=_REVIEW_THRESHOLD,
        )
        assert len(result) == 4

    async def test_weight_and_indices_present(self) -> None:
        left = [{"name": "Alice", "dob": "1990"}]
        right = [{"name": "Alice", "dob": "1990"}]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            left_rows=left,
            right_rows=right,
            field_specs=_SPECS,
            match_threshold=_MATCH_THRESHOLD,
            review_threshold=_REVIEW_THRESHOLD,
        )
        assert "weight" in result[0]
        assert result[0]["left_index"] == 0
        assert result[0]["right_index"] == 0

    async def test_wired_tapestry_run(self) -> None:
        @knot
        async def emit_left() -> list[dict[str, Any]]:
            return [{"name": "Alice", "dob": "1990"}]

        @knot
        async def emit_right() -> list[dict[str, Any]]:
            return [{"name": "Alice", "dob": "1990"}]

        with Tapestry() as t:
            l_knot = emit_left(_config=KnotConfig(id="left_rows"))
            r_knot = emit_right(_config=KnotConfig(id="right_rows"))
            k = ProbabilisticLinker(
                left_rows=l_knot,
                right_rows=r_knot,
                field_specs=_SPECS,
                match_threshold=_MATCH_THRESHOLD,
                review_threshold=_REVIEW_THRESHOLD,
                _config=KnotConfig(id="linker"),
            )
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id][0]["classification"] == "match"


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_left_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_left() -> list[dict[str, Any]]:
            return []

        with Tapestry() as t:
            l_knot = emit_left(_config=KnotConfig(id="left_rows"))
            k = ProbabilisticLinker(
                left_rows=l_knot,
                right_rows=_right_param(),
                field_specs=_SPECS,
                match_threshold=_MATCH_THRESHOLD,
                review_threshold=_REVIEW_THRESHOLD,
                _config=KnotConfig(id="linker"),
            )
        _ = t
        assert k is not None


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> ProbabilisticLinker:
        defaults: dict[str, Any] = {
            "field_specs": _SPECS,
            "match_threshold": _MATCH_THRESHOLD,
            "review_threshold": _REVIEW_THRESHOLD,
        }
        defaults.update(kwargs)
        with Tapestry():
            return ProbabilisticLinker(
                left_rows=_left_param(),
                right_rows=_right_param(),
                **defaults,
                _config=KnotConfig(id="val"),
            )

    async def _call(self, k: ProbabilisticLinker, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "left_rows": [],
            "right_rows": [],
            "field_specs": _SPECS,
            "match_threshold": _MATCH_THRESHOLD,
            "review_threshold": _REVIEW_THRESHOLD,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_invalid_column_name(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, field_specs=[{"column": "bad col", "m": 0.9, "u": 0.1}])

    async def test_rejects_out_of_range_m(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, r"'m'"):
            await self._call(k, field_specs=[{"column": "name", "m": 1.5, "u": 0.1}])

    async def test_rejects_thresholds_inverted(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "match_threshold"):
            await self._call(k, match_threshold=0.0, review_threshold=5.0)
