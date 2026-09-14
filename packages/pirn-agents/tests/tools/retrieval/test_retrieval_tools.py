"""Mirrored tests for retriever_tool and rag_tool (PIR-171).

Uses the shared ``StubMemoryStore``/``StubLLMProvider`` doubles (no vendor SDK) to
verify ranked retrieval, RAG composition (retrieval + generation behind one
call), provider-neutral prompting, and typed F1 result shapes.
"""

from __future__ import annotations

from pirn_agents.tools.retrieval.rag_tool import RagTool
from pirn_agents.tools.retrieval.retriever_tool import RetrieverTool
from pirn_agents.tools.tool_call import ToolCall
from tests.conftest import StubLLMProvider, StubMemoryStore
from tests.tools.tool_runner import ToolRunner


async def _store_with(docs: list[dict[str, str]]) -> StubMemoryStore:
    store = StubMemoryStore()
    for i, doc in enumerate(docs):
        await store.store(f"k{i}", doc)
    return store


class TestRetrieverTool:
    async def test_returns_ranked_results(self) -> None:
        store = await _store_with([{"text": "alpha"}, {"text": "beta"}, {"text": "gamma"}])
        tool = RetrieverTool.bind(store=store, top_k=2)
        result = await ToolRunner.value(tool, {"query": "greek"})
        assert result["count"] == 2
        assert result["results"][0]["text"] == "alpha"
        assert store.searched == ["greek"]

    async def test_top_k_override(self) -> None:
        store = await _store_with([{"text": str(i)} for i in range(10)])
        # ADR WS1: ``top_k`` is a tunable default the call may override, not bound policy.
        tool = RetrieverTool.bind(store=store).defaults(top_k=5)
        result = await ToolRunner.value(tool, {"query": "q", "top_k": 3})
        assert result["count"] == 3

    async def test_as_tool_result_shape(self) -> None:
        store = await _store_with([{"text": "x"}])
        tool = RetrieverTool.bind(store=store)
        call = ToolCall(tool_name="retriever", arguments={"query": "q"}, call_id="c1")
        outcome = await ToolRunner.view(tool, call)
        assert outcome.status == "ok"
        assert outcome.result["count"] == 1

    def test_rejects_non_store(self) -> None:
        import pytest

        with pytest.raises(TypeError):
            RetrieverTool.bind(store=object())  # type: ignore[arg-type]


class TestRagTool:
    async def test_composes_retrieval_and_generation(self) -> None:
        store = await _store_with([{"text": "The sky is blue."}])
        llm = StubLLMProvider(["The sky is blue."])
        tool = RagTool.bind(store=store, llm=llm, top_k=3)
        result = await ToolRunner.value(tool, {"question": "What color is the sky?"})
        assert result["question"] == "What color is the sky?"
        assert result["answer"] == "The sky is blue."
        assert result["sources"] == [{"text": "The sky is blue."}]
        # The retrieved context must reach the LLM prompt.
        user_msg = llm.calls[0][-1]["content"]
        assert "The sky is blue." in user_msg
        assert store.searched == ["What color is the sky?"]

    async def test_handles_no_context(self) -> None:
        store = StubMemoryStore()
        llm = StubLLMProvider(["I don't know."])
        tool = RagTool.bind(store=store, llm=llm)
        result = await ToolRunner.value(tool, {"question": "unknown?"})
        assert result["sources"] == []
        assert result["answer"] == "I don't know."

    def test_rejects_non_llm(self) -> None:
        import pytest

        with pytest.raises(TypeError):
            RagTool.bind(store=StubMemoryStore(), llm=object())  # type: ignore[arg-type]
