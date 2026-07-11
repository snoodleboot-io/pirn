"""Unit tests for :class:`SubGraphContextBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.sub_graph_context_builder import (
    SubGraphContextBuilder,
)


class _GraphSource(Knot):
    def __init__(self, nodes, *, _config, **kwargs):
        self._nodes = nodes
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._nodes


class TestSubGraphContextBuilderProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_hop_count(self) -> None:
        knot = SubGraphContextBuilder(
            retrieved=_GraphSource([], _config=KnotConfig(id="src")),
            _config=KnotConfig(id="sgcb"),
        )
        with self.assertRaisesRegex(ValueError, "hop_count"):
            await knot.process(retrieved=[], hop_count=0)

    async def test_partitions_entities_and_relations(self) -> None:
        nodes = [
            {"type": "entity", "id": "e1", "label": "Person"},
            {"type": "relation", "src": "e1", "dst": "e2", "rel": "knows"},
        ]
        with Tapestry() as t:
            src = _GraphSource(nodes, _config=KnotConfig(id="src"))
            SubGraphContextBuilder(
                retrieved=src,
                hop_count=2,
                _config=KnotConfig(id="sgcb"),
            )
        result = await t.run(RunRequest())
        block = result.outputs["sgcb"]
        kinds = [item.get("kind") or item.get("hops") for item in block]
        assert 2 in kinds  # hop_count header
        assert "entity" in kinds
        assert "relation" in kinds

    async def test_includes_hop_count_header(self) -> None:
        with Tapestry() as t:
            src = _GraphSource([], _config=KnotConfig(id="src"))
            SubGraphContextBuilder(
                retrieved=src,
                hop_count=3,
                _config=KnotConfig(id="sgcb"),
            )
        result = await t.run(RunRequest())
        block = result.outputs["sgcb"]
        assert block[0] == {"hops": 3}

    async def test_rejects_non_mapping_item(self) -> None:
        with Tapestry() as t:
            src = _GraphSource(["not-a-mapping"], _config=KnotConfig(id="src"))
            SubGraphContextBuilder(
                retrieved=src,
                hop_count=1,
                _config=KnotConfig(id="sgcb"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
