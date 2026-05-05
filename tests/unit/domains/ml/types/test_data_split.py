"""Tests for :class:`DataSplit`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset


class TestDataSplit(unittest.TestCase):
    def test_construction_and_audit_dict(self) -> None:
        fetched_at = datetime(2026, 4, 29, 0, 0, tzinfo=timezone.utc)
        train = MLDataset(
            name="d:train",
            feature_names=("a",),
            row_count=80,
            source_uri="x",
            fetched_at=fetched_at,
        )
        test = MLDataset(
            name="d:test",
            feature_names=("a",),
            row_count=20,
            source_uri="x",
            fetched_at=fetched_at,
        )
        split = DataSplit(train=train, test=test)
        assert split.validation is None
        audit = split._pirn_audit_dict()
        assert audit["train"]["name"] == "d:train"
        assert audit["test"]["name"] == "d:test"
        assert audit["validation"] is None
