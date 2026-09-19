"""Tests for :class:`PoolValidator`."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.connectors.database_connection_pool import DatabaseConnectionPool

from pirn_data.pool_validator import PoolValidator


class TestValidatePools(unittest.TestCase):
    def test_accepts_valid_pools(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        PoolValidator.validate_pools("Example", source_pool=pool, target_pool=pool)

    def test_rejects_non_pool_source(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        with self.assertRaisesRegex(TypeError, "source_pool must be a DatabaseConnectionPool"):
            PoolValidator.validate_pools("Example", source_pool="nope", target_pool=pool)

    def test_rejects_non_pool_target(self) -> None:
        pool = MagicMock(spec=DatabaseConnectionPool)
        with self.assertRaisesRegex(TypeError, "target_pool must be a DatabaseConnectionPool"):
            PoolValidator.validate_pools("Example", source_pool=pool, target_pool="nope")

    def test_reports_the_first_keyword_in_the_order_given(self) -> None:
        with self.assertRaisesRegex(TypeError, "target_pool must be a DatabaseConnectionPool"):
            PoolValidator.validate_pools("Example", target_pool="nope", source_pool="also-nope")


class TestValidateOptionalPools(unittest.TestCase):
    def test_none_is_accepted(self) -> None:
        PoolValidator.validate_optional_pools("Example", dim_pool=None)

    def test_a_pool_is_accepted(self) -> None:
        PoolValidator.validate_optional_pools(
            "Example", dim_pool=MagicMock(spec=DatabaseConnectionPool)
        )

    def test_a_non_pool_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "Example: dim_pool must be a"):
            PoolValidator.validate_optional_pools("Example", dim_pool="nope")


class TestValidateNonEmptyString(unittest.TestCase):
    def test_accepts_non_empty(self) -> None:
        PoolValidator.validate_non_empty_string("Example", "source_query", "SELECT 1")

    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_query must be a non-empty string"):
            PoolValidator.validate_non_empty_string("Example", "source_query", "")

    def test_rejects_non_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_query must be a non-empty string"):
            PoolValidator.validate_non_empty_string("Example", "source_query", 123)


class TestValidateIdentifier(unittest.TestCase):
    def test_accepts_single_identifier(self) -> None:
        PoolValidator.validate_identifier("target_table", "customers")

    def test_rejects_single_bad_identifier(self) -> None:
        with self.assertRaises(ValueError):
            PoolValidator.validate_identifier("target_table", "bad;name")

    def test_accepts_sequence(self) -> None:
        PoolValidator.validate_identifier("primary_keys", ("id", "region"))

    def test_rejects_empty_sequence(self) -> None:
        with self.assertRaises(ValueError):
            PoolValidator.validate_identifier("primary_keys", ())

    def test_rejects_non_sequence(self) -> None:
        not_a_sequence: Any = 123
        with self.assertRaises(TypeError):
            PoolValidator.validate_identifier("primary_keys", not_a_sequence)
