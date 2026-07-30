"""Unit tests for RunRetention."""

from __future__ import annotations

import unittest

import pytest
from pydantic import ValidationError

from pirn.backends.base.run_history import RunHistory
from pirn.backends.base.run_retention import RunRetention
from pirn.backends.in_memory.in_memory_history import InMemoryHistory


class TestRunRetention(unittest.TestCase):
    def test_defaults_to_unbounded(self) -> None:
        retention = RunRetention()
        self.assertIsNone(retention.max_runs)
        self.assertFalse(retention.is_bounded)

    def test_bounded_when_a_ceiling_is_declared(self) -> None:
        retention = RunRetention(max_runs=5)
        self.assertEqual(retention.max_runs, 5)
        self.assertTrue(retention.is_bounded)

    def test_frozen(self) -> None:
        retention = RunRetention(max_runs=5)
        with pytest.raises(ValidationError):
            retention.max_runs = 10  # type: ignore[misc]

    def test_rejects_a_non_positive_ceiling(self) -> None:
        with pytest.raises(ValidationError):
            RunRetention(max_runs=0)


class TestRetentionCapability(unittest.TestCase):
    """The engine asks the store what it can keep — never what class it is."""

    def test_base_run_history_declares_durable(self) -> None:
        self.assertFalse(RunHistory().retention.is_bounded)

    def test_in_memory_history_declares_a_bound(self) -> None:
        retention = InMemoryHistory().retention
        self.assertTrue(retention.is_bounded)
        self.assertEqual(retention.max_runs, InMemoryHistory.DEFAULT_MAX_RUNS)

    def test_bound_is_configurable(self) -> None:
        self.assertEqual(InMemoryHistory(max_runs=7).retention.max_runs, 7)

    def test_rejects_a_non_positive_bound(self) -> None:
        with pytest.raises(ValueError, match="max_runs must be positive"):
            InMemoryHistory(max_runs=0)
