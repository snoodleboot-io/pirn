"""Tests for :class:`LookupEnricher`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.feature_engineering.lookup_enricher import LookupEnricher
from pirn.tapestry import Tapestry

_LOOKUP = [
    {"country_code": "US", "country_name": "United States", "region": "Americas"},
    {"country_code": "GB", "country_name": "United Kingdom", "region": "Europe"},
]


def _make_knot(**overrides: Any) -> LookupEnricher:
    defaults: dict[str, Any] = {
        "lookup_table": _LOOKUP,
        "join_keys": ("country_code",),
        "enrich_columns": ("country_name", "region"),
    }
    defaults.update(overrides)
    return LookupEnricher(rows=[], **defaults, _config=KnotConfig(id="enricher"))


class TestLookupEnricher(unittest.IsolatedAsyncioTestCase):
    async def test_matching_row_enriched(self) -> None:
        rows = [{"country_code": "US", "revenue": 100}]
        k = _make_knot()
        result = await k.process(
            rows=rows,
            lookup_table=_LOOKUP,
            join_keys=("country_code",),
            enrich_columns=("country_name", "region"),
        )
        assert result[0]["country_name"] == "United States"
        assert result[0]["region"] == "Americas"

    async def test_no_match_yields_none(self) -> None:
        rows = [{"country_code": "XX", "revenue": 50}]
        k = _make_knot()
        result = await k.process(
            rows=rows,
            lookup_table=_LOOKUP,
            join_keys=("country_code",),
            enrich_columns=("country_name",),
        )
        assert result[0]["country_name"] is None

    async def test_non_join_columns_unchanged(self) -> None:
        rows = [{"country_code": "GB", "revenue": 200}]
        k = _make_knot()
        result = await k.process(
            rows=rows,
            lookup_table=_LOOKUP,
            join_keys=("country_code",),
            enrich_columns=("country_name",),
        )
        assert result[0]["revenue"] == 200

    async def test_multiple_rows_mixed_match(self) -> None:
        rows = [
            {"country_code": "US"},
            {"country_code": "JP"},
            {"country_code": "GB"},
        ]
        k = _make_knot()
        result = await k.process(
            rows=rows,
            lookup_table=_LOOKUP,
            join_keys=("country_code",),
            enrich_columns=("region",),
        )
        assert result[0]["region"] == "Americas"
        assert result[1]["region"] is None
        assert result[2]["region"] == "Europe"

    async def test_empty_input(self) -> None:
        k = _make_knot()
        result = await k.process(
            rows=[],
            lookup_table=_LOOKUP,
            join_keys=("country_code",),
            enrich_columns=("country_name",),
        )
        assert result == []

    async def test_tapestry_run(self) -> None:
        rows = [{"country_code": "US"}]
        with Tapestry() as t:
            LookupEnricher(
                rows=rows,
                lookup_table=_LOOKUP,
                join_keys=("country_code",),
                enrich_columns=("country_name",),
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [{"country_code": "GB"}]

        with Tapestry() as t:
            rows_knot = emit_rows(_config=KnotConfig(id="rows"))
            LookupEnricher(
                rows=rows_knot,
                lookup_table=_LOOKUP,
                join_keys=("country_code",),
                enrich_columns=("country_name",),
                _config=KnotConfig(id="enricher"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["enricher"][0]["country_name"] == "United Kingdom"


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> LookupEnricher:
        defaults: dict[str, Any] = {
            "lookup_table": _LOOKUP,
            "join_keys": ("country_code",),
            "enrich_columns": ("country_name",),
        }
        defaults.update(kwargs)
        with Tapestry():
            return LookupEnricher(rows=[], **defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: LookupEnricher, **overrides: Any) -> Any:
        args: dict[str, Any] = {
            "rows": [{"country_code": "US"}],
            "lookup_table": _LOOKUP,
            "join_keys": ("country_code",),
            "enrich_columns": ("country_name",),
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_invalid_join_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, join_keys=("bad col",))

    async def test_rejects_non_list_lookup(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "list"):
            await self._call(k, lookup_table="not-a-list")
