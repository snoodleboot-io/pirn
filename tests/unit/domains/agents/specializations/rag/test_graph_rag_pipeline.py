"""Tests for :class:`GraphRAGPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.rag.graph_rag_pipeline import (
    GraphRAGPipeline,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubMemoryStore,
)


class TestGraphRAGPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_subgraph_passed_to_llm(self) -> None:
        memory = StubMemoryStore(
            [
                {
                    "type": "entity",
                    "id": "alice",
                    "label": "Person",
                    "attrs": {"role": "engineer"},
                },
                {
                    "type": "relation",
                    "src": "alice",
                    "dst": "acme",
                    "rel": "works_at",
                },
                {
                    "type": "entity",
                    "id": "acme",
                    "label": "Company",
                    "attrs": {},
                },
            ]
        )
        llm = StubLLMProvider(["Alice works at Acme."])
        with Tapestry() as t:
            GraphRAGPipeline(
                query="where does alice work",
                graph_memory=memory,
                llm=llm,
                hop_count=2,
                _config=KnotConfig(id="grag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["grag"]
        assert isinstance(response, AgentResponse)
        assert response.content == "Alice works at Acme."
        prompt_body = llm.calls[0][-1]["content"]
        assert "alice" in prompt_body
        assert "acme" in prompt_body
        assert "works_at" in prompt_body
        assert "hops=2" in prompt_body


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_query(self) -> None:
        memory = StubMemoryStore([])
        llm = StubLLMProvider(["answer"])
        with Tapestry():
            k = GraphRAGPipeline.__new__(GraphRAGPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, AttributeError)):
            await k.process(query=42, graph_memory=memory, llm=llm, hop_count=2)  # type: ignore[arg-type]
