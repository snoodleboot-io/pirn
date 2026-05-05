"""Tests for :class:`MLDataset`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.domains.ml.types.ml_dataset import MLDataset


class TestMLDataset(unittest.TestCase):
    def test_construction_and_audit_dict(self) -> None:
        fetched_at = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        dataset = MLDataset(
            name="customers",
            feature_names=("age", "income"),
            target_name="churned",
            row_count=1000,
            source_uri="db://prod/customers",
            fetched_at=fetched_at,
        )
        audit = dataset._pirn_audit_dict()
        assert audit == {
            "name": "customers",
            "feature_names": ["age", "income"],
            "target_name": "churned",
            "row_count": 1000,
            "source_uri": "db://prod/customers",
            "fetched_at": fetched_at.isoformat(),
        }
