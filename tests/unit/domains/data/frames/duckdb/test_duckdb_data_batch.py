"""Tests for :class:`DuckdbDataBatch`."""

from __future__ import annotations

import unittest
from datetime import UTC

import duckdb

from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


class TestDuckdbDataBatch(unittest.TestCase):
    def test_column_names_reflect_relation(self) -> None:
        connection = duckdb.connect(database=":memory:")
        connection.execute("CREATE TABLE t AS SELECT 1 AS id, 'alice' AS name")
        relation = connection.table("t")
        batch = DuckdbDataBatch(
            relation=relation, connection=connection, source_uri="memory://test"
        )
        assert set(batch.column_names) == {"id", "name"}

    def test_default_fetched_at_is_utc(self) -> None:
        connection = duckdb.connect(database=":memory:")
        relation = connection.sql("SELECT 1 AS x")
        batch = DuckdbDataBatch(relation=relation, connection=connection)
        assert batch.fetched_at.tzinfo is UTC

    def test_with_relation_preserves_metadata(self) -> None:
        connection = duckdb.connect(database=":memory:")
        original_relation = connection.sql("SELECT 1 AS x")
        original = DuckdbDataBatch(
            relation=original_relation,
            connection=connection,
            source_uri="duckdb://h/db",
        )
        new_relation = connection.sql("SELECT 1 AS x UNION ALL SELECT 2")
        replaced = original.with_relation(new_relation)
        assert replaced.connection is connection
        assert replaced.source_uri == original.source_uri
        assert replaced.fetched_at == original.fetched_at

    def test_dataclass_is_frozen(self) -> None:
        connection = duckdb.connect(database=":memory:")
        relation = connection.sql("SELECT 1 AS x")
        batch = DuckdbDataBatch(relation=relation, connection=connection)
        try:
            batch.relation = connection.sql("SELECT 2 AS x")  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("expected FrozenInstanceError")
