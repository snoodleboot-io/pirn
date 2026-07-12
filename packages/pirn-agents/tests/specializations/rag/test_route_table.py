"""Tests for :class:`RouteTable`."""

from __future__ import annotations

import unittest

from pirn_agents.specializations.rag.route_table import RouteTable
from tests.specializations.conftest import StubMemoryStore


class TestRouteTable(unittest.TestCase):
    def test_names_and_lookup(self) -> None:
        docs = StubMemoryStore([{"id": "1"}])
        code = StubMemoryStore([{"id": "2"}])
        table = RouteTable({"docs": docs, "code": code})
        assert table.route_names() == ["docs", "code"]
        assert table.has("code")
        assert not table.has("tickets")
        assert table.store_for("docs") is docs

    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            RouteTable({})

    def test_rejects_non_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "must map to a MemoryStore"):
            RouteTable({"bad": "nope"})  # type: ignore[dict-item]

    def test_unknown_route_raises(self) -> None:
        table = RouteTable({"docs": StubMemoryStore([])})
        with self.assertRaisesRegex(KeyError, "unknown route"):
            table.store_for("missing")
