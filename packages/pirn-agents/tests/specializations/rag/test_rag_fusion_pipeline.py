"""Tests for :class:`RagFusionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.rag_fusion_pipeline import RagFusionPipeline
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class TestRagFusionPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_expands_fuses_and_synthesizes(self) -> None:
        memory = StubMemoryStore(
            [{"id": "1", "text": "qubits stable"}, {"id": "2", "text": "1000 qubit chip"}]
        )
        llm = StubLLMProvider(["variant a\nvariant b\nvariant c", "fused answer"])
        with Tapestry() as t:
            RagFusionPipeline(
                query="quantum facts",
                memory=memory,
                llm=llm,
                num_queries=4,
                top_k=3,
                _config=KnotConfig(id="fusion"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["fusion"]
        assert isinstance(response, AgentResponse)
        assert response.content == "fused answer"
        # Original + 3 variants -> 4 searches.
        assert len(memory.search_queries) == 4
        assert memory.search_queries[0] == "quantum facts"

    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["a", "b"])
        knot = RagFusionPipeline(
            query="q",
            memory=StubMemoryStore([]),
            llm=llm,
            _config=KnotConfig(id="fusion"),
        )
        with self.assertRaisesRegex(TypeError, "memory must be a MemoryStore"):
            await knot.process(query="q", memory="nope", llm=llm)  # type: ignore[arg-type]
