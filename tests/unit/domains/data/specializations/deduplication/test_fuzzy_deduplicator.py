"""Tests for :class:`FuzzyDeduplicator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.deduplication.fuzzy_deduplicator import (
    FuzzyDeduplicator,
)
from pirn.tapestry import Tapestry

_MATCH_COLUMN = "name"


def _rows_param() -> Parameter:
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make_knot(**kwargs: Any) -> FuzzyDeduplicator:
    defaults: dict[str, Any] = {
        "match_column": _MATCH_COLUMN,
        "blocking_key_length": 3,
        "similarity_metric": "jaro_winkler",
        "threshold": 0.85,
    }
    defaults.update(kwargs)
    return FuzzyDeduplicator(
        rows=_rows_param(),
        **defaults,
        _config=KnotConfig(id="fuzzy"),
    )


class TestFuzzyDeduplicator(unittest.IsolatedAsyncioTestCase):
    async def test_exact_duplicates_merged(self) -> None:
        rows = [{"name": "alice"}, {"name": "alice"}]
        with Tapestry():
            k = _make_knot(threshold=0.9)
        result = await k.process(
            rows=rows,
            match_column=_MATCH_COLUMN,
            blocking_key_length=3,
            similarity_metric="jaro_winkler",
            threshold=0.9,
        )
        assert len(result) == 1

    async def test_near_duplicate_merged_levenshtein(self) -> None:
        rows = [{"name": "alice"}, {"name": "alic3"}]
        with Tapestry():
            k = _make_knot(similarity_metric="levenshtein", threshold=0.7)
        result = await k.process(
            rows=rows,
            match_column=_MATCH_COLUMN,
            blocking_key_length=3,
            similarity_metric="levenshtein",
            threshold=0.7,
        )
        assert len(result) == 1

    async def test_distinct_names_not_merged(self) -> None:
        rows = [{"name": "alice"}, {"name": "bob"}]
        with Tapestry():
            k = _make_knot(threshold=0.9)
        result = await k.process(
            rows=rows,
            match_column=_MATCH_COLUMN,
            blocking_key_length=3,
            similarity_metric="jaro_winkler",
            threshold=0.9,
        )
        assert len(result) == 2

    async def test_jaro_winkler_near_duplicate(self) -> None:
        rows = [{"name": "jennifer"}, {"name": "jenifer"}]
        with Tapestry():
            k = _make_knot(similarity_metric="jaro_winkler", threshold=0.90)
        result = await k.process(
            rows=rows,
            match_column=_MATCH_COLUMN,
            blocking_key_length=3,
            similarity_metric="jaro_winkler",
            threshold=0.90,
        )
        assert len(result) == 1

    async def test_empty_input(self) -> None:
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=[],
            match_column=_MATCH_COLUMN,
            blocking_key_length=3,
            similarity_metric="jaro_winkler",
            threshold=0.85,
        )
        assert result == []

    async def test_wired_tapestry_run(self) -> None:
        @knot
        async def emit_rows() -> list[dict[str, Any]]:
            return [{"name": "alice"}, {"name": "alice"}]

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = FuzzyDeduplicator(
                rows=r_knot,
                match_column=_MATCH_COLUMN,
                blocking_key_length=3,
                similarity_metric="jaro_winkler",
                threshold=0.9,
                _config=KnotConfig(id="fuzzy"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs[k.config.id]) == 1


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_match_column_from_upstream_knot(self) -> None:
        @knot
        async def emit_col() -> str:
            return _MATCH_COLUMN

        with Tapestry() as t:
            mc_knot = emit_col(_config=KnotConfig(id="mc"))
            k = FuzzyDeduplicator(
                rows=_rows_param(),
                match_column=mc_knot,
                blocking_key_length=3,
                similarity_metric="jaro_winkler",
                threshold=0.85,
                _config=KnotConfig(id="fuzzy"),
            )
        _ = t
        assert k is not None


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> FuzzyDeduplicator:
        defaults: dict[str, Any] = {
            "match_column": _MATCH_COLUMN,
            "blocking_key_length": 3,
            "similarity_metric": "jaro_winkler",
            "threshold": 0.85,
        }
        defaults.update(kwargs)
        with Tapestry():
            return FuzzyDeduplicator(
                rows=_rows_param(),
                **defaults,
                _config=KnotConfig(id="val"),
            )

    async def _call(self, k: FuzzyDeduplicator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "match_column": _MATCH_COLUMN,
            "blocking_key_length": 3,
            "similarity_metric": "jaro_winkler",
            "threshold": 0.85,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_invalid_match_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, match_column="bad col")

    async def test_rejects_invalid_metric(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "similarity_metric"):
            await self._call(k, similarity_metric="hamming")

    async def test_rejects_threshold_out_of_range(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "threshold"):
            await self._call(k, threshold=1.1)

    async def test_rejects_zero_blocking_length(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "blocking_key_length"):
            await self._call(k, blocking_key_length=0)
