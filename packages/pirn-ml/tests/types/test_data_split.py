"""Tests for :class:`SplitManifest`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class TestDataSplit(unittest.TestCase):
    def test_construction_and_audit_dict(self) -> None:
        fetched_at = datetime(2026, 4, 29, 0, 0, tzinfo=UTC)
        train = DatasetManifest(
            name="d:train",
            feature_names=("a",),
            row_count=80,
            source_uri="x",
            fetched_at=fetched_at,
        )
        test = DatasetManifest(
            name="d:test",
            feature_names=("a",),
            row_count=20,
            source_uri="x",
            fetched_at=fetched_at,
        )
        split = SplitManifest(train=train, test=test)
        assert split.validation is None
        audit = split._pirn_audit_dict()
        assert audit["train"]["name"] == "d:train"
        assert audit["test"]["name"] == "d:test"
        assert audit["validation"] is None
