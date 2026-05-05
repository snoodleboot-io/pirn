"""Tests for :class:`LookupEnricher`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.feature_engineering.lookup_enricher import (
    LookupEnricher,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(lookup_table, join_keys, enrich_columns):
    with Tapestry():
        knot = LookupEnricher(
            rows=_rows_param(),
            lookup_table=lookup_table,
            join_keys=join_keys,
            enrich_columns=enrich_columns,
            _config=KnotConfig(id="enricher"),
        )
    return knot


_LOOKUP = [
    {"country_code": "US", "country_name": "United States", "region": "Americas"},
    {"country_code": "GB", "country_name": "United Kingdom", "region": "Europe"},
]


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_join_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            _make(_LOOKUP, ["bad col"], ["country_name"])

    def test_rejects_non_list_lookup(self) -> None:
        with self.assertRaisesRegex(TypeError, "list"):
            with Tapestry():
                LookupEnricher(
                    rows=_rows_param(),
                    lookup_table="not-a-list",  # type: ignore[arg-type]
                    join_keys=["country_code"],
                    enrich_columns=["country_name"],
                    _config=KnotConfig(id="x"),
                )


class TestBehaviour(unittest.IsolatedAsyncioTestCase):
    async def test_matching_row_enriched(self) -> None:
        rows = [{"country_code": "US", "revenue": 100}]
        knot = _make(_LOOKUP, ["country_code"], ["country_name", "region"])
        result = await knot.process(rows=rows)
        assert result[0]["country_name"] == "United States"
        assert result[0]["region"] == "Americas"

    async def test_no_match_yields_none(self) -> None:
        rows = [{"country_code": "XX", "revenue": 50}]
        knot = _make(_LOOKUP, ["country_code"], ["country_name"])
        result = await knot.process(rows=rows)
        assert result[0]["country_name"] is None

    async def test_non_join_columns_unchanged(self) -> None:
        rows = [{"country_code": "GB", "revenue": 200}]
        knot = _make(_LOOKUP, ["country_code"], ["country_name"])
        result = await knot.process(rows=rows)
        assert result[0]["revenue"] == 200

    async def test_multiple_rows_mixed_match(self) -> None:
        rows = [
            {"country_code": "US"},
            {"country_code": "JP"},
            {"country_code": "GB"},
        ]
        knot = _make(_LOOKUP, ["country_code"], ["region"])
        result = await knot.process(rows=rows)
        assert result[0]["region"] == "Americas"
        assert result[1]["region"] is None
        assert result[2]["region"] == "Europe"

    async def test_empty_input(self) -> None:
        knot = _make(_LOOKUP, ["country_code"], ["country_name"])
        result = await knot.process(rows=[])
        assert result == []

    async def test_empty_lookup(self) -> None:
        rows = [{"country_code": "US"}]
        knot = _make([], ["country_code"], ["country_name"])
        result = await knot.process(rows=rows)
        assert result[0]["country_name"] is None
