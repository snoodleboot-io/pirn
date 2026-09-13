"""Tests for :class:`_PoolMergeKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

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
