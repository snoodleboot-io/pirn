"""Tests for :class:`SelfQueryRagPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.self_query_rag_pipeline import SelfQueryRagPipeline
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.vector_stores.vector_record import VectorRecord
from tests.specializations.conftest import StubEmbeddingProvider, StubLLMProvider


class TestSelfQueryRagPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_filter_retrieves_and_synthesizes(self) -> None:
        embedder = StubEmbeddingProvider(dimension=4)
        store = InMemoryVectorStore(embedder=embedder)
        vectors = await embedder.embed(["ho paper", "sohl paper"])
        await store.upsert(
            [
                VectorRecord.create(
                    id="a", vector=vectors[0], metadata={"author": "Ho"}, document="ho paper"
                ),
                VectorRecord.create(
                    id="b", vector=vectors[1], metadata={"author": "Sohl"}, document="sohl paper"
                ),
            ]
        )
        llm = StubLLMProvider(['{"query": "paper", "filter": {"author": "Ho"}}', "grounded answer"])
        with Tapestry() as t:
            SelfQueryRagPipeline(
                query="papers by Ho",
                store=store,
                embedder=StubEmbeddingProvider(dimension=4),
                llm=llm,
                filterable_fields=["author"],
                top_k=5,
                _config=KnotConfig(id="selfquery"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["selfquery"]
        assert isinstance(response, AgentResponse)
        assert response.content == "grounded answer"
        # Synthesis prompt should only carry the Ho document.
        synth_prompt = llm.calls[-1][-1]["content"]
        assert "ho paper" in synth_prompt
        assert "sohl paper" not in synth_prompt

    async def test_rejects_non_vector_store(self) -> None:
        knot = SelfQueryRagPipeline(
            query="q",
            store=InMemoryVectorStore(embedder=StubEmbeddingProvider(dimension=4)),
            embedder=StubEmbeddingProvider(dimension=4),
            llm=StubLLMProvider(["{}", "a"]),
            _config=KnotConfig(id="selfquery"),
        )
        with self.assertRaisesRegex(TypeError, "store must be a VectorMemoryStore"):
            await knot.process(
                query="q",
                store="nope",  # type: ignore[arg-type]
                embedder=StubEmbeddingProvider(dimension=4),
                llm=StubLLMProvider(["{}", "a"]),
            )
