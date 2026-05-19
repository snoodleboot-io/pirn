"""Tests for :class:`DatasetManifest`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.domains.ml.types.dataset_manifest import DatasetManifest


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
        }
