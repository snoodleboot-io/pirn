"""Tests for :class:`DuckdbCast`."""

from __future__ import annotations
import unittest

import duckdb

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.duckdb.duckdb_cast import DuckdbCast
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.tapestry import Tapestry


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
        type_by_column = dict(zip(out.column_names, out.relation.types))
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
        type_by_column = dict(zip(out.column_names, out.relation.types))
        assert "DECIMAL" in str(type_by_column["amount"]).upper()


class TestConstruction(unittest.TestCase):
    def test_rejects_non_string_type(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "type-name string"):
                DuckdbCast(
                    batch=batch,
                    casts={"a": int},  # type: ignore[dict-item]
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_injection_token_in_type(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "DuckDB type"):
                DuckdbCast(
                    batch=batch,
                    casts={"a": "INTEGER); DROP TABLE t; --"},
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_unknown_token_shape(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "DuckDB type"):
                DuckdbCast(
                    batch=batch,
                    casts={"a": "int'"},
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_empty_casts(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "non-empty"):
                DuckdbCast(
                    batch=batch,
                    casts={},
                    _config=KnotConfig(id="c"),
                )
