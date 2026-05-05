"""Tests for :class:`ExactDeduplicator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.deduplication.exact_deduplicator import (
    ExactDeduplicator,
)
from pirn.tapestry import Tapestry

_KEY_COLUMNS = ("id",)
_TIEBREAKER = "score"


def _rows_param() -> Parameter:
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make_knot(**kwargs: Any) -> ExactDeduplicator:
    defaults: dict[str, Any] = {
        "key_columns": _KEY_COLUMNS,
        "tiebreaker_column": _TIEBREAKER,
        "tiebreaker_direction": "desc",
    }
    defaults.update(kwargs)
    return ExactDeduplicator(
        rows=_rows_param(),
        **defaults,
        _config=KnotConfig(id="dedup"),
    )


class TestExactDeduplicator(unittest.IsolatedAsyncioTestCase):
    async def test_no_duplicates_returns_all(self) -> None:
        rows = [{"id": 1, "score": 10}, {"id": 2, "score": 20}]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=rows,
            key_columns=_KEY_COLUMNS,
            tiebreaker_column=_TIEBREAKER,
            tiebreaker_direction="desc",
        )
        assert len(result) == 2

    async def test_keeps_highest_score_on_desc(self) -> None:
        rows = [
            {"id": 1, "score": 5},
            {"id": 1, "score": 9},
            {"id": 2, "score": 3},
        ]
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=rows,
            key_columns=_KEY_COLUMNS,
            tiebreaker_column=_TIEBREAKER,
            tiebreaker_direction="desc",
        )
        id1 = next(r for r in result if r["id"] == 1)
        assert id1["score"] == 9

    async def test_keeps_lowest_score_on_asc(self) -> None:
        rows = [{"id": 1, "score": 5}, {"id": 1, "score": 9}]
        with Tapestry():
            k = _make_knot(tiebreaker_direction="asc")
        result = await k.process(
            rows=rows,
            key_columns=_KEY_COLUMNS,
            tiebreaker_column=_TIEBREAKER,
            tiebreaker_direction="asc",
        )
        assert result[0]["score"] == 5

    async def test_composite_key(self) -> None:
        rows = [
            {"a": 1, "b": 2, "v": 1},
            {"a": 1, "b": 2, "v": 2},
            {"a": 1, "b": 3, "v": 1},
        ]
        with Tapestry():
            k = _make_knot(key_columns=("a", "b"), tiebreaker_column="v")
        result = await k.process(
            rows=rows,
            key_columns=("a", "b"),
            tiebreaker_column="v",
            tiebreaker_direction="desc",
        )
        assert len(result) == 2

    async def test_empty_input(self) -> None:
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=[],
            key_columns=_KEY_COLUMNS,
            tiebreaker_column=_TIEBREAKER,
            tiebreaker_direction="desc",
        )
        assert result == []

    async def test_wired_tapestry_run(self) -> None:
        @knot
        async def emit_rows() -> list[dict[str, Any]]:
            return [{"id": 1, "score": 5}, {"id": 1, "score": 9}]

        with Tapestry() as t:
            r_knot = emit_rows(_config=KnotConfig(id="rows"))
            k = ExactDeduplicator(
                rows=r_knot,
                key_columns=_KEY_COLUMNS,
                tiebreaker_column=_TIEBREAKER,
                tiebreaker_direction="desc",
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs[k.config.id]) == 1


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_key_columns_from_upstream_knot(self) -> None:
        @knot
        async def emit_keys() -> tuple[str, ...]:
            return ("id",)

        with Tapestry() as t:
            kc_knot = emit_keys(_config=KnotConfig(id="keys"))
            k = ExactDeduplicator(
                rows=_rows_param(),
                key_columns=kc_knot,
                tiebreaker_column=_TIEBREAKER,
                tiebreaker_direction="desc",
                _config=KnotConfig(id="dedup"),
            )
        _ = t  # wiring only; no run needed for wiring test
        assert k is not None


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> ExactDeduplicator:
        defaults: dict[str, Any] = {
            "key_columns": _KEY_COLUMNS,
            "tiebreaker_column": _TIEBREAKER,
            "tiebreaker_direction": "desc",
        }
        defaults.update(kwargs)
        with Tapestry():
            return ExactDeduplicator(
                rows=_rows_param(),
                **defaults,
                _config=KnotConfig(id="val"),
            )

    async def _call(self, k: ExactDeduplicator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "rows": [],
            "key_columns": _KEY_COLUMNS,
            "tiebreaker_column": _TIEBREAKER,
            "tiebreaker_direction": "desc",
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_invalid_key_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, key_columns=["bad col"])

    async def test_rejects_invalid_tiebreaker(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, tiebreaker_column="bad col")

    async def test_rejects_invalid_direction(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "tiebreaker_direction"):
            await self._call(k, tiebreaker_direction="up")
