"""Tests for :class:`LanceDataset` adapter."""

from __future__ import annotations

import unittest
from typing import Any

from pirn_data.specialized.lance.lance_dataset import LanceDataset
from pydantic import TypeAdapter


class _FakeLanceDataset:
    """Stand-in for a real ``lance.LanceDataset``."""

    def __init__(self, name: str = "fake") -> None:
        self.name = name


class TestLanceDatasetConstruction(unittest.TestCase):
    def test_default_metadata(self) -> None:
        handle = LanceDataset(dataset=_FakeLanceDataset())
        assert handle.source_uri == ""
        assert handle.fetched_at is not None

    def test_propagates_source_uri(self) -> None:
        handle = LanceDataset(dataset=_FakeLanceDataset(), source_uri="/tmp/x.lance")
        assert handle.source_uri == "/tmp/x.lance"

    def test_dataset_attribute_round_trips(self) -> None:
        inner = _FakeLanceDataset(name="payload")
        handle = LanceDataset(dataset=inner)
        assert handle.dataset is inner


class TestLanceDatasetPydanticSchema(unittest.TestCase):
    def test_is_instance_schema_passes_for_real_instance(self) -> None:
        adapter: TypeAdapter[Any] = TypeAdapter(LanceDataset)
        handle = LanceDataset(dataset=_FakeLanceDataset())
        assert adapter.validate_python(handle) is handle

    def test_is_instance_schema_rejects_other_types(self) -> None:
        adapter: TypeAdapter[Any] = TypeAdapter(LanceDataset)
        with self.assertRaises((TypeError, ValueError)):
            adapter.validate_python({"dataset": "no"})
