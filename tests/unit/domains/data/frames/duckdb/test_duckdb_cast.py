"""Tests for :class:`DuckdbCast`."""

from __future__ import annotations

import unittest

try:
    import duckdb
except ImportError as _e:
    raise unittest.SkipTest("duckdb not installed") from _e

import duckdb
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.frames.duckdb.duckdb_cast import DuckdbCast
from pirn_data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


@knot
async def emit_string_columns() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS "
        "SELECT * FROM (VALUES ('1', '12.5'), ('2', '99.0')) AS v(id, amount)"
    )
    return DuckdbDataBatch(
        relation=connection.table("t"), connection=connection
    )


def _make_batch() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS "
        "SELECT * FROM (VALUES ('1', '12.5')) AS v(id, amount)"
    )
    return DuckdbDataBatch(relation=connection.table("t"), connection=connection)


class TestDuckdbCast(unittest.IsolatedAsyncioTestCase):
    async def test_casts_columns_to_duckdb_types(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="src"))
            DuckdbCast(
                batch=batch,
                casts={"id": "INTEGER", "amount": "DOUBLE"},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["casted"]
        # DuckDB returns lower-case logical type names.
        type_by_column = dict(zip(out.column_names, out.relation.types, strict=False))
        assert "INTEGER" in str(type_by_column["id"]).upper()
        assert "DOUBLE" in str(type_by_column["amount"]).upper()

    async def test_columns_not_in_relation_are_skipped(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="src"))
            DuckdbCast(
                batch=batch,
                casts={"absent": "INTEGER"},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["casted"]
        # No-op; verify the relation is materialisable and untouched.
        assert set(out.column_names) == {"id", "amount"}

    async def test_decimal_with_precision(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="src"))
            DuckdbCast(
                batch=batch,
                casts={"amount": "DECIMAL(10, 2)"},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["casted"]
        type_by_column = dict(zip(out.column_names, out.relation.types, strict=False))
        assert "DECIMAL" in str(type_by_column["amount"]).upper()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_casts_from_upstream_knot(self) -> None:
        @knot
        async def emit_casts() -> dict:
            return {"id": "INTEGER"}

        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="src"))
            casts_knot = emit_casts(_config=KnotConfig(id="casts"))
            DuckdbCast(
                batch=batch,
                casts=casts_knot,
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["casted"]
        type_by_column = dict(zip(out.column_names, out.relation.types, strict=False))
        assert "INTEGER" in str(type_by_column["id"]).upper()


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: object) -> DuckdbCast:
        @knot
        async def upstream() -> DuckdbDataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return DuckdbCast(
                batch=batch, casts={"id": "INTEGER"},
                _config=KnotConfig(id="c"), **kwargs,
            )

    async def test_rejects_non_mapping_casts(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_make_batch(), casts="bad")

    async def test_rejects_empty_casts(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_make_batch(), casts={})

    async def test_rejects_non_string_type(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "type-name string"):
            await k.process(batch=_make_batch(), casts={"id": int})  # type: ignore[dict-item]

    async def test_rejects_injection_token_in_type(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "DuckDB type"):
            await k.process(
                batch=_make_batch(),
                casts={"id": "INTEGER); DROP TABLE t; --"},
            )

    async def test_rejects_unknown_token_shape(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "DuckDB type"):
            await k.process(batch=_make_batch(), casts={"id": "int'"})

    async def test_rejects_injection_in_column_name(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "forbidden"):
            await k.process(
                batch=_make_batch(),
                casts={'id"; DROP TABLE t; --': "INTEGER"},
            )
