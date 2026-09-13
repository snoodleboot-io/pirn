"""Tests for :class:`_PoolMergeKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.connectors.database_connection_pool import DatabaseConnectionPool

from pirn_data.specializations._pool_merge_knot import _PoolMergeKnot


class TestValidatePools(unittest.TestCase):
    def test_accepts_valid_pools(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        _PoolMergeKnot._validate_pools("Example", source_pool=pool, target_pool=pool)

    def test_rejects_non_pool_source(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        with self.assertRaisesRegex(TypeError, "source_pool must be a DatabaseConnectionPool"):
            _PoolMergeKnot._validate_pools("Example", source_pool="nope", target_pool=pool)

    def test_rejects_non_pool_target(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        with self.assertRaisesRegex(TypeError, "target_pool must be a DatabaseConnectionPool"):
            _PoolMergeKnot._validate_pools("Example", source_pool=pool, target_pool="nope")

    def test_checks_in_keyword_order(self) -> None:
        with self.assertRaisesRegex(TypeError, "target_pool must be a DatabaseConnectionPool"):
            _PoolMergeKnot._validate_pools("Example", target_pool="nope", source_pool="also-nope")


class TestValidateNonEmptyString(unittest.TestCase):
    def test_accepts_non_empty_string(self) -> None:
        _PoolMergeKnot._validate_non_empty_string("Example", "source_query", "SELECT 1")

    def test_rejects_empty_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_query must be a non-empty string"):
            _PoolMergeKnot._validate_non_empty_string("Example", "source_query", "")

    def test_rejects_non_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_query must be a non-empty string"):
            _PoolMergeKnot._validate_non_empty_string("Example", "source_query", 123)


class TestValidateIdentifier(unittest.TestCase):
    def test_validates_single_column(self) -> None:
        _PoolMergeKnot._validate_identifier("target_table", "customers")

    def test_rejects_bad_single_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a plain identifier"):
            _PoolMergeKnot._validate_identifier("target_table", "bad;name")

    def test_validates_column_sequence(self) -> None:
        _PoolMergeKnot._validate_identifier("primary_keys", ("id", "region"))

    def test_rejects_empty_column_sequence(self) -> None:
        with self.assertRaisesRegex(ValueError, "primary_keys: must be non-empty"):
            _PoolMergeKnot._validate_identifier("primary_keys", ())

    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "primary_keys: must be a sequence of column names"):
            _PoolMergeKnot._validate_identifier("primary_keys", 123)  # type: ignore[arg-type]


class TestIndexRowsByKey(unittest.TestCase):
    def test_indexes_by_key_positions(self) -> None:
        rows = [(1, "alice"), (2, "bob")]
        indexed = _PoolMergeKnot._index_rows_by_key(rows, key_indices=(0,))
        assert indexed == {(1,): (1, "alice"), (2,): (2, "bob")}

    def test_later_duplicate_key_overwrites_earlier(self) -> None:
        rows = [(1, "alice"), (1, "alicia")]
        indexed = _PoolMergeKnot._index_rows_by_key(rows, key_indices=(0,))
        assert indexed == {(1,): (1, "alicia")}

    def test_empty_rows_yields_empty_index(self) -> None:
        assert _PoolMergeKnot._index_rows_by_key([], key_indices=(0,)) == {}


class TestValidateRowWidth(unittest.TestCase):
    def test_accepts_matching_width(self) -> None:
        _PoolMergeKnot._validate_row_width("Example", (1, "alice"), ("id", "name"))

    def test_rejects_mismatched_width(self) -> None:
        with self.assertRaisesRegex(ValueError, "row width 1 does not match column_names width 2"):
            _PoolMergeKnot._validate_row_width("Example", (1,), ("id", "name"))


class TestNonKeyValuesChanged(unittest.TestCase):
    def test_reports_unchanged(self) -> None:
        existing = (1, "alice")
        row = (1, "alice")
        assert _PoolMergeKnot._non_key_values_changed(existing, row, non_key_indices=(1,)) is False

    def test_reports_changed(self) -> None:
        existing = (1, "alice")
        row = (1, "alicia")
        assert _PoolMergeKnot._non_key_values_changed(existing, row, non_key_indices=(1,)) is True


class TestExecutePerRowUpsert(unittest.IsolatedAsyncioTestCase):
    async def test_updates_existing_and_inserts_new(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        pool.fetch_all = AsyncMock(side_effect=[[(1,)], []])
        pool.execute = AsyncMock()
        source_rows = [(1, "alice-updated"), (2, "bob")]
        matched = await _PoolMergeKnot._execute_per_row_upsert(
            source_rows,
            pool,
            key_tuple=("id",),
            non_key_tuple=("name",),
            select_existing_query="SELECT 1 FROM t WHERE id = ?",
            update_query="UPDATE t SET name = ? WHERE id = ?",
            insert_query="INSERT INTO t (id, name) VALUES (?, ?)",
        )
        assert matched == [True, False]
        pool.execute.assert_any_await("UPDATE t SET name = ? WHERE id = ?", ("alice-updated", 1))
        pool.execute.assert_any_await("INSERT INTO t (id, name) VALUES (?, ?)", (2, "bob"))

    async def test_empty_rows_issues_no_statements(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        pool.fetch_all = AsyncMock()
        pool.execute = AsyncMock()
        matched = await _PoolMergeKnot._execute_per_row_upsert(
            [],
            pool,
            key_tuple=("id",),
            non_key_tuple=("name",),
            select_existing_query="SELECT 1 FROM t WHERE id = ?",
            update_query="UPDATE t SET name = ? WHERE id = ?",
            insert_query="INSERT INTO t (id, name) VALUES (?, ?)",
        )
        assert matched == []
        pool.fetch_all.assert_not_called()
        pool.execute.assert_not_called()
