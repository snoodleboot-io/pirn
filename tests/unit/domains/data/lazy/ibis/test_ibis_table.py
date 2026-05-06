"""Tests for :class:`IbisTable`."""

from __future__ import annotations

import unittest
from datetime import UTC

import ibis

from pirn.domains.data.lazy.ibis.ibis_table import IbisTable


def _users_table() -> ibis.Table:
    con = ibis.duckdb.connect()
    con.create_table("users", {"id": [1, 2, 3], "name": ["a", "b", "c"]})
    return con.table("users")


class TestIbisTable(unittest.TestCase):
    def test_column_names_from_expression(self) -> None:
        batch = IbisTable(expression=_users_table(), backend_name="duckdb")
        assert set(batch.column_names) == {"id", "name"}

    def test_default_fetched_at_is_utc(self) -> None:
        batch = IbisTable(expression=_users_table())
        assert batch.fetched_at.tzinfo is UTC

    def test_with_expression_preserves_metadata(self) -> None:
        original = IbisTable(
            expression=_users_table(),
            backend_name="duckdb",
            source_uri="duckdb:///memory",
        )
        replaced = original.with_expression(
            original.expression.filter(original.expression.id > 1)
        )
        assert replaced.backend_name == "duckdb"
        assert replaced.source_uri == "duckdb:///memory"
        assert replaced.fetched_at == original.fetched_at

    def test_schema_property_returns_ibis_schema(self) -> None:
        batch = IbisTable(expression=_users_table())
        schema = batch.schema
        # Ibis schemas expose ``.names`` as a tuple/list of column names.
        assert "id" in tuple(schema.names)
        assert "name" in tuple(schema.names)
