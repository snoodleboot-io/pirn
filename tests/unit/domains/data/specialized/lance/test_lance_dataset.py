"""Tests for :class:`LanceDataset` adapter."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter

from pirn.domains.data.specialized.lance.lance_dataset import LanceDataset


class _FakeLanceDataset:
    """Stand-in for a real ``lance.LanceDataset``."""

    def __init__(self, name: str = "fake") -> None:
        self.name = name


class TestLanceDatasetConstruction:
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


class TestLanceDatasetPydanticSchema:
    def test_is_instance_schema_passes_for_real_instance(self) -> None:
        adapter: TypeAdapter[Any] = TypeAdapter(LanceDataset)
        handle = LanceDataset(dataset=_FakeLanceDataset())
        assert adapter.validate_python(handle) is handle

    def test_is_instance_schema_rejects_other_types(self) -> None:
        adapter: TypeAdapter[Any] = TypeAdapter(LanceDataset)
        with pytest.raises(Exception):
            adapter.validate_python({"dataset": "no"})
