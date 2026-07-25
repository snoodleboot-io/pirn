"""Mirrored tests for span emission across LLM / tool / retrieval calls (PIR-311).

Uses stub doubles (StubLLMProvider / StubTool / StubMemoryStore) driven through
a :class:`Tracer` wired to a recording sink, asserting spans fire with the right
kind/metadata around each call type — and that the default no-op sink needs no
backend.
"""

from __future__ import annotations

from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.observability.tracer import Tracer
from tests.conftest import StubLLMProvider, StubMemoryStore, StubTool
from tests.observability._recording_sink import RecordingSink


class TestDefaultNoOp:
    async def test_default_tracer_needs_no_sink_or_backend(self) -> None:
        tracer = Tracer()  # no sink supplied -> no-op default
        async with tracer.llm_span(name="llm.chat") as span:
            span.set_attribute("ok", True)
        assert span.status is SpanStatus.OK  # completed with zero backend wiring


class TestSpanEmission:
    async def test_llm_call_emits_llm_span(self) -> None:
        sink = RecordingSink()
        tracer = Tracer(sink)
        provider = StubLLMProvider(["hello"])
        async with tracer.llm_span(name="llm.chat", attributes={"model": "stub"}) as span:
            reply = await provider.chat([{"role": "user", "content": "hi"}])
            span.set_attribute("tokens", len(str(reply)))
        assert len(sink.started) == 1
        assert len(sink.finished) == 1
        assert span.kind is SpanKind.LLM
        assert span.status is SpanStatus.OK
        assert span.attributes["model"] == "stub"

    async def test_tool_invocation_emits_tool_span(self) -> None:
        sink = RecordingSink()
        tracer = Tracer(sink)
        tool = StubTool(name="search")
        async with tracer.tool_span(name="tool:search") as span:
            await tool.invoke({"input": "x"})
        assert sink.finished[0].kind is SpanKind.TOOL
        assert span.status is SpanStatus.OK

    async def test_retrieval_emits_retrieval_span(self) -> None:
        sink = RecordingSink()
        tracer = Tracer(sink)
        store = StubMemoryStore()
        await store.store("k", {"v": 1})
        async with tracer.retrieval_span(name="retrieve", attributes={"top_k": 5}) as span:
            await store.retrieve("k")
        assert span.kind is SpanKind.RETRIEVAL
        assert span.attributes["top_k"] == 5

    async def test_error_body_finishes_error_status(self) -> None:
        sink = RecordingSink()
        tracer = Tracer(sink)
        try:
            async with tracer.llm_span() as span:
                raise ValueError("boom")
        except ValueError:
            pass
        assert span.status is SpanStatus.ERROR
        assert sink.finished[0].status is SpanStatus.ERROR

    async def test_nested_spans_record_parent(self) -> None:
        sink = RecordingSink()
        tracer = Tracer(sink)
        async with tracer.llm_span(name="outer") as outer:
            async with tracer.tool_span(name="inner") as inner:
                assert inner.parent_id == outer.span_id
        # After both close the stack is empty, so a new span is a root again.
        async with tracer.retrieval_span(name="after") as after:
            assert after.parent_id is None


class TestIdFactory:
    async def test_injected_id_factory_used(self) -> None:
        ids = iter(["a", "b", "c"])
        tracer = Tracer(id_factory=lambda: next(ids))
        async with tracer.llm_span() as span:
            assert span.span_id == "a"
