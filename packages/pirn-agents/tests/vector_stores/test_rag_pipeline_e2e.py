"""End-to-end RAG on :class:`InMemoryVectorStore` with no external service (S3-T3).

Satisfies the feature acceptance criterion: a full ``NaiveRAGPipeline`` —
retrieve -> prompt -> generate -> package — runs in CI against the zero-service
in-memory store. The store embeds via a deterministic in-process embedder and
the LLM is a stub, so the whole pipeline is offline and deterministic.
"""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.naive_rag_pipeline import NaiveRAGPipeline
from pirn_agents.vector_stores.in_memory_vector_store import InMemoryVectorStore
from pirn_agents.vector_stores.vector_record import VectorRecord
from tests.specializations.conftest import StubLLMProvider
from tests.vector_stores.conformance import FixedEmbedder


class TestRagPipelineEndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_naive_rag_runs_end_to_end_on_in_memory_store(self) -> None:
        store = InMemoryVectorStore(embedder=FixedEmbedder([1.0, 0.0, 0.0]))
        await store.upsert(
            [
                VectorRecord.create(
                    id="doc-1",
                    vector=[1.0, 0.0, 0.0],
                    metadata={"topic": "pirn"},
                    document="pirn agents run retrieval augmented generation",
                ),
                VectorRecord.create(
                    id="doc-2",
                    vector=[0.9, 0.1, 0.0],
                    metadata={"topic": "pirn"},
                    document="the in-memory vector store needs no external service",
                ),
            ]
        )
        llm = StubLLMProvider(["Retrieval-augmented answer."])

        with Tapestry() as tapestry:
            NaiveRAGPipeline(
                query="how do pirn agents retrieve?",
                memory=store,
                llm=llm,
                top_k=2,
                _config=KnotConfig(id="rag"),
            )
        result = await tapestry.run(RunRequest())

        assert result.succeeded
        response = result.outputs["rag"]
        assert response is not None
        # the LLM was invoked and the retrieved documents were folded into its prompt
        assert llm.calls, "LLM was never called end-to-end"
        prompt_text = " ".join(str(message.get("content", "")) for message in llm.calls[0])
        assert "retrieval augmented generation" in prompt_text


if __name__ == "__main__":
    unittest.main()
