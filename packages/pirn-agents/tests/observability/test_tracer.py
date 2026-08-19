"""Mirrored tests for span emission across LLM / tool / retrieval calls (PIR-311).

Uses stub doubles (StubLLMProvider / StubTool / StubMemoryStore) driven through
a :class:`Tracer` wired to a recording sink, asserting spans fire with the right
kind/metadata around each call type — and that the default no-op sink needs no
backend.

:class:`TestConcurrentNesting` covers PIR-788: the nesting stack must be
task-local and balanced on both the ``async with`` and the ``start_span`` /
``Span.finish`` paths.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context, copy_context

from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.observability.tracer import Tracer
from tests.conftest import StubLLMProvider, StubMemoryStore, StubTool
from tests.observability._recording_sink import RecordingSink


async def _record_child_parent(tracer: Tracer, index: int, parents: list[str | None]) -> None:
    """Open a child span, yield to the loop mid-span, then record its parent.

    The ``await`` is the whole point: it forces the sibling tasks to interleave
    *inside* one another's spans, which is the only arrangement that exposes a
    nesting stack shared across tasks.
    """
    async with tracer.tool_span(name=f"tool:{index}") as span:
        await asyncio.sleep(0)
        parents.append(span.parent_id)


def _parent_of_a_detached_span(tracer: Tracer) -> str | None:
    """Open and finish a span off the event loop, returning its ``parent_id``.

    Run through a :class:`~contextvars.Context` by the caller to model a
    dispatcher hop — a copied context (``ThreadDispatcher``) or an empty one (a
    process-boundary backend such as Ray/Dask/Celery).
    """
    span = tracer.start_span(name="detached")
    span.finish(SpanStatus.OK)
    return span.parent_id


def _finish_from_this_context(span: Span) -> None:
    """Close ``span`` from whatever context this happens to run in.

    Driven through a copied :class:`~contextvars.Context` on a worker thread to
    model the shape that actually occurs: a span opened on the event loop and
    closed on a ``ThreadDispatcher`` worker (PIR-767).
    """
    span.finish(SpanStatus.OK)


class TestCrossContextFinish:
    """A span finished in a different context than it was opened in (PIR-788).

    The existing coverage only opens *and* closes inside the hopped context,
    which is why the stranding went unnoticed: rebuilding the stack in the
    finishing context leaves the opener's own stack holding the entry forever,
    and every context later copied from it inherits the corpse.
    """

    async def test_finishing_in_a_copied_context_drains_the_openers_stack(self) -> None:
        tracer = Tracer(RecordingSink())
        outer = tracer.start_span(name="outer")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(copy_context().run, _finish_from_this_context, outer).result()
        assert tracer.open_span_ids == ()

    async def test_the_next_span_is_not_parented_to_a_closed_span(self) -> None:
        tracer = Tracer(RecordingSink())
        outer = tracer.start_span(name="outer")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(copy_context().run, _finish_from_this_context, outer).result()
        after = tracer.start_span(name="after")
        assert after.parent_id is None
        after.finish(SpanStatus.OK)

    async def test_the_residue_does_not_propagate_into_a_later_hop(self) -> None:
        # A context copied *after* the cross-context finish must not inherit the
        # closed entry either — otherwise the residue is permanent and spreads
        # to every task or thread the opener later spawns.
        tracer = Tracer(RecordingSink())
        outer = tracer.start_span(name="outer")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(copy_context().run, _finish_from_this_context, outer).result()
            parent = pool.submit(copy_context().run, _parent_of_a_detached_span, tracer).result()
        assert parent is None

    async def test_the_residue_does_not_propagate_into_a_later_task(self) -> None:
        tracer = Tracer(RecordingSink())
        outer = tracer.start_span(name="outer")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(copy_context().run, _finish_from_this_context, outer).result()
        parents: list[str | None] = []
        # `asyncio` copies the context per task, so a task created after the
        # cross-context finish is the other way the corpse escapes.
        await asyncio.gather(*(_record_child_parent(tracer, index, parents) for index in range(3)))
        assert parents == [None] * 3

    async def test_a_cross_context_finish_leaves_the_enclosing_span_open(self) -> None:
        # Draining must be surgical: closing the inner span from elsewhere may
        # not take the still-open outer one with it.
        tracer = Tracer(RecordingSink())
        outer = tracer.start_span(name="outer")
        inner = tracer.start_span(name="inner")
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(copy_context().run, _finish_from_this_context, inner).result()
        assert tracer.open_span_ids == (outer.span_id,)
        outer.finish(SpanStatus.OK)
        assert tracer.open_span_ids == ()


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


class TestConcurrentNesting:
    async def test_concurrent_children_all_parent_to_the_enclosing_span(self) -> None:
        tracer = Tracer(RecordingSink())
        parents: list[str | None] = []
        async with tracer.llm_span(name="outer") as outer:
            await asyncio.gather(
                *(_record_child_parent(tracer, index, parents) for index in range(4))
            )
        # Siblings are siblings: none of them may nest under another sibling
        # just because it happened to be mid-flight when they started.
        assert parents == [outer.span_id] * 4

    async def test_concurrent_fanout_leaves_the_stack_at_its_pre_fanout_depth(self) -> None:
        tracer = Tracer(RecordingSink())
        parents: list[str | None] = []
        async with tracer.llm_span(name="outer") as outer:
            await asyncio.gather(
                *(_record_child_parent(tracer, index, parents) for index in range(4))
            )
            # The fan-out is over, so the next span is a direct child of `outer`
            # again — not of some finished sibling still stranded on the stack.
            async with tracer.tool_span(name="serial") as serial:
                assert serial.parent_id == outer.span_id
        async with tracer.retrieval_span(name="after") as after:
            assert after.parent_id is None

    async def test_start_span_finish_pairs_do_not_grow_the_stack(self) -> None:
        # The hook path: `start_span` pushes, and only `Span.finish` can pop it.
        tracer = Tracer(RecordingSink())
        for index in range(5):
            span = tracer.start_span(name=f"hook:{index}", kind=SpanKind.TOOL)
            assert span.parent_id is None
            span.finish(SpanStatus.OK)
        async with tracer.llm_span(name="after") as after:
            assert after.parent_id is None

    async def test_repeated_hook_cycles_leave_the_stack_bounded(self) -> None:
        tracer = Tracer(RecordingSink())
        for index in range(50):
            span = tracer.start_span(name=f"hook:{index}", kind=SpanKind.TOOL)
            assert tracer.open_span_ids == (span.span_id,)
            span.finish(SpanStatus.OK)
            assert tracer.open_span_ids == ()

    async def test_finishing_twice_pops_once(self) -> None:
        tracer = Tracer(RecordingSink())
        async with tracer.llm_span(name="outer") as outer:
            inner = tracer.start_span(name="inner", kind=SpanKind.TOOL)
            inner.finish(SpanStatus.OK)
            inner.finish(SpanStatus.OK)
            assert tracer.open_span_ids == (outer.span_id,)

    async def test_error_finish_on_the_hook_path_also_pops(self) -> None:
        tracer = Tracer(RecordingSink())
        failed = tracer.start_span(name="hook:boom", kind=SpanKind.TOOL)
        failed.finish(SpanStatus.ERROR)
        async with tracer.llm_span(name="after") as after:
            assert after.parent_id is None

    async def test_parenting_survives_a_context_copying_thread_hop(self) -> None:
        # ThreadDispatcher runs the knot inside `copy_context()` (PIR-767), so
        # ambient nesting must cross that hop intact.
        tracer = Tracer(RecordingSink())
        with ThreadPoolExecutor(max_workers=1) as pool:
            async with tracer.llm_span(name="outer") as outer:
                context = copy_context()
                parent = pool.submit(context.run, _parent_of_a_detached_span, tracer).result()
        assert parent == outer.span_id

    async def test_parenting_degrades_to_none_across_a_process_boundary(self) -> None:
        # Ray/Dask/Celery dispatch into an interpreter that never saw our
        # context; an empty `Context` reproduces exactly that starting state.
        # The span must come out unparented rather than inheriting a stale id.
        tracer = Tracer(RecordingSink())
        with ThreadPoolExecutor(max_workers=1) as pool:
            async with tracer.llm_span(name="outer"):
                parent = pool.submit(Context().run, _parent_of_a_detached_span, tracer).result()
        assert parent is None

    async def test_separate_tracers_do_not_share_a_stack(self) -> None:
        first = Tracer(RecordingSink())
        second = Tracer(RecordingSink())
        async with first.llm_span(name="first.outer"):
            async with second.tool_span(name="second.inner") as inner:
                assert inner.parent_id is None


class TestIdFactory:
    async def test_injected_id_factory_used(self) -> None:
        ids = iter(["a", "b", "c"])
        tracer = Tracer(id_factory=lambda: next(ids))
        async with tracer.llm_span() as span:
            assert span.span_id == "a"
