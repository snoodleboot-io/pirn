"""Unit tests for ValueRetention."""

from __future__ import annotations

import unittest

import pytest
from pydantic import ValidationError

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.value_retention import ValueRetention
from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore


class TestValueRetention(unittest.TestCase):
    def test_defaults_to_unbounded(self) -> None:
        retention = ValueRetention()
        self.assertIsNone(retention.max_values)
        self.assertFalse(retention.is_bounded)

    def test_bounded_when_a_ceiling_is_declared(self) -> None:
        retention = ValueRetention(max_values=5)
        self.assertEqual(retention.max_values, 5)
        self.assertTrue(retention.is_bounded)

    def test_frozen(self) -> None:
        retention = ValueRetention(max_values=5)
        with pytest.raises(ValidationError):
            retention.max_values = 10  # type: ignore[misc]

    def test_rejects_a_non_positive_ceiling(self) -> None:
        with pytest.raises(ValidationError):
            ValueRetention(max_values=0)


class TestValueRetentionCapability(unittest.TestCase):
    """A consumer asks the store what it keeps — never what class it is."""

    def test_base_data_store_declares_durable(self) -> None:
        self.assertFalse(DataStore().retention.is_bounded)

    def test_a_backend_that_says_nothing_inherits_durable(self) -> None:
        class ThirdPartyStore(DataStore):
            """A backend core has never heard of, declaring nothing."""

        self.assertFalse(ThirdPartyStore().retention.is_bounded)

    def test_in_memory_data_store_declares_a_bound(self) -> None:
        retention = InMemoryDataStore().retention
        self.assertTrue(retention.is_bounded)
        self.assertEqual(retention.max_values, InMemoryDataStore.DEFAULT_MAX_VALUES)

    def test_bound_is_configurable(self) -> None:
        self.assertEqual(InMemoryDataStore(max_values=7).retention.max_values, 7)

    def test_rejects_a_non_positive_bound(self) -> None:
        with pytest.raises(ValueError, match="max_values must be positive"):
            InMemoryDataStore(max_values=0)
