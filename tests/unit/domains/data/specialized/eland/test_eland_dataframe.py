"""Tests for :class:`ElandDataFrame` adapter."""

from __future__ import annotations

import unittest
from typing import Any

from pirn_data.specialized.eland.eland_dataframe import ElandDataFrame
from pydantic import TypeAdapter


class _FakeElandFrame:
    """Stand-in for a real ``eland.DataFrame``."""

    def __init__(self, name: str = "fake") -> None:
        self.name = name


class TestElandDataFrameConstruction(unittest.TestCase):
    def test_default_metadata(self) -> None:
        handle = ElandDataFrame(frame=_FakeElandFrame())
        assert handle.source_uri == ""
        assert handle.fetched_at is not None

    def test_propagates_source_uri(self) -> None:
        handle = ElandDataFrame(frame=_FakeElandFrame(), source_uri="elasticsearch://orders")
        assert handle.source_uri == "elasticsearch://orders"

    def test_frame_attribute_round_trips(self) -> None:
        inner = _FakeElandFrame(name="payload")
        handle = ElandDataFrame(frame=inner)
        assert handle.frame is inner


class TestElandDataFramePydanticSchema(unittest.TestCase):
    def test_is_instance_schema_passes_for_real_instance(self) -> None:
        adapter: TypeAdapter[Any] = TypeAdapter(ElandDataFrame)
        handle = ElandDataFrame(frame=_FakeElandFrame())
        assert adapter.validate_python(handle) is handle

    def test_is_instance_schema_rejects_other_types(self) -> None:
        adapter: TypeAdapter[Any] = TypeAdapter(ElandDataFrame)
        with self.assertRaises((TypeError, ValueError)):
            adapter.validate_python({"frame": "no"})
