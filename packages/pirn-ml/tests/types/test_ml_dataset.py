"""Tests for :class:`DatasetManifest`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_ml.types.dataset_manifest import DatasetManifest


class TestMLDataset(unittest.TestCase):
    def test_construction_and_audit_dict(self) -> None:
        fetched_at = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)
        dataset = DatasetManifest(
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
            "row_indices": [],
        }

    def test_row_indices_are_part_of_the_audit_identity(self) -> None:
        fetched_at = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)
        first = DatasetManifest(
            name="d:fold0:test", row_count=2, fetched_at=fetched_at, row_indices=(0, 3)
        )
        second = DatasetManifest(
            name="d:fold0:test", row_count=2, fetched_at=fetched_at, row_indices=(1, 2)
        )
        assert first._pirn_audit_dict()["row_indices"] == [0, 3]
        assert first._pirn_audit_dict() != second._pirn_audit_dict()
