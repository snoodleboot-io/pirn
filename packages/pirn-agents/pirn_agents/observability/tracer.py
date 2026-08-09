"""``Tracer`` — opens :class:`Span`\\ s around LLM, tool, and retrieval calls."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import partial
from typing import Any
from uuid import uuid4

from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.open_span_entry import OpenSpanEntry
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus

# The open spans of the *current task*, outermost first, as
# :class:`OpenSpanEntry` objects.
#
# A ContextVar rather than instance state because the whole point of the span
# plane is to observe concurrent fan-out: `asyncio` copies the context per task,
# so sibling tasks each get their own view and cannot mis-parent one another's
# spans (PIR-788). Entries carry the owning tracer's key so two tracers alive in
# one task keep separate trees, and it is a module-level var (never one per
# instance) so a short-lived tracer cannot pin an entry in a long-lived context.
#
# The value is an immutable tuple, rebuilt on every push, so a child task's
# spans never write back into the parent's stack.
#
# Closing, though, must reach *every* context — which is why an entry is an
# object and not a plain tuple. Rebuilding the tuple only affects the context
# doing the rebuilding, so a span finished on a `ThreadDispatcher` worker (the
# `copy_context()` shape from PIR-767) used to leave its entry stranded in the
# opener's context permanently, mis-parenting everything the opener started
# afterwards and propagating into every context later copied from it. Marking
# the shared entry closed is visible through every copy at once, so the drain
# happens wherever `finish` is called from.
_current_span_stack: ContextVar[tuple[OpenSpanEntry, ...]] = ContextVar(
    "_pirn_agents_current_span_stack", default=()
)


class Tracer:
    """The span/callback interface every instrumented call site goes through.

    A tracer owns one :class:`ObservabilitySink` (a no-op by default, so tracing
    is zero-cost until a real sink is plugged in) and mints spans against it. It
    exposes both styles the codebase needs:

    * a synchronous start/finish pair (:meth:`start_span` + ``Span.finish``)
      that mirrors F1's ``on_start``/``on_finish`` hook shape — used by the
      tool-invocation-hook adapter; and
    * an ``async with`` :meth:`span` context manager that auto-finishes with
      :attr:`SpanStatus.OK` on clean exit or :attr:`SpanStatus.ERROR` if the
      body raises — used to wrap LLM and retrieval calls.

    Nesting is tracked on a *task-local* stack (see ``_current_span_stack``) so
    child spans record their ``parent_id`` automatically without concurrent
    tasks interfering with one another. Finishing a span drains it from that
    stack in every context that can see it, not only the one calling ``finish``,
    so a span opened on the event loop and closed on a dispatcher worker leaves
    nothing behind. Sink callbacks are best-effort: any exception a sink raises
    is swallowed so observability can never abort a traced call.
    """

    def __init__(
        self,
        sink: ObservabilitySink | None = None,
        *,
        id_factory: Callable[[], str] | None = None,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._sink = sink if sink is not None else ObservabilitySink()
        self._id_factory = id_factory if id_factory is not None else (lambda: uuid4().hex)
        self._monotonic = monotonic
        self._stack_key = uuid4().hex

    @property
    def sink(self) -> ObservabilitySink:
        """The sink spans are reported to."""
        return self._sink

    @property
    def open_span_ids(self) -> tuple[str, ...]:
        """Ids of this tracer's spans open in the current task, outermost first.

        Empty in a context that never opened one — including a task, thread, or
        interpreter reached through a dispatcher that does not propagate
        contextvars, where spans correctly come out unparented rather than
        inheriting a stale id from somewhere else. Entries closed from another
        context are skipped, so a span finished elsewhere is never reported open
        here.
        """
        return tuple(
            entry.span_id
            for entry in _current_span_stack.get()
            if entry.tracer_key == self._stack_key and not entry.closed
        )

    @staticmethod
    def _prune() -> None:
        """Drop closed entries from *this* context's view of the stack.

        Purely housekeeping — :attr:`open_span_ids` already ignores closed
        entries, so this only stops them accumulating. It cannot substitute for
        :meth:`OpenSpanEntry.close`: a ``set`` here is invisible to every other
        context, which is the whole defect being fixed.
        """
        _current_span_stack.set(
            tuple(entry for entry in _current_span_stack.get() if not entry.closed)
        )

    def _push(self, entry: OpenSpanEntry) -> None:
        """Make ``entry`` this tracer's innermost open span in this context."""
        self._prune()
        _current_span_stack.set((*_current_span_stack.get(), entry))

    def _pop(self, entry: OpenSpanEntry, span: Span) -> None:
        """Close ``entry``, wherever in the context tree it is still visible.

        Bound to its entry and fired from :class:`Span`'s ``on_close``, which
        the span guarantees runs at most once, so the push in
        :meth:`start_span` is always balanced — including on the hook path,
        where nothing else would ever pop.

        Closing the shared entry is what makes this correct across contexts: the
        local tuple rebuild below only cleans up the finishing context, so on
        its own it would strand the entry in the context that opened the span.

        Args:
            entry: This span's slot on the stack, bound at ``start_span``.
            span: The finishing span, supplied by the ``on_close`` contract and
                not needed here — ``entry`` already identifies the slot.
        """
        entry.close()
        self._prune()

    def start_span(
        self,
        *,
        name: str,
        kind: SpanKind = SpanKind.GENERIC,
        attributes: Mapping[str, Any] | None = None,
    ) -> Span:
        """Open and return a span; the caller is responsible for ``finish``.

        The span's ``parent_id`` is taken from the top of this task's nesting
        stack, and its id is pushed so any span started before it finishes nests
        beneath it. The push is balanced by the span's ``on_close``, so this
        path pops even though no context manager wraps it. The sink's
        ``on_start`` is fired (exceptions swallowed) before returning.
        """
        open_ids = self.open_span_ids
        parent_id = open_ids[-1] if open_ids else None
        span_id = self._id_factory()
        entry = OpenSpanEntry(self._stack_key, span_id)
        span = Span(
            name=name,
            kind=kind,
            span_id=span_id,
            sink=self._sink,
            parent_id=parent_id,
            attributes=attributes,
            monotonic=self._monotonic,
            on_close=partial(self._pop, entry),
        )
        self._push(entry)
        try:
            self._sink.on_start(span)
        except Exception:
            pass
        return span

    @asynccontextmanager
    async def span(
        self,
        *,
        name: str,
        kind: SpanKind = SpanKind.GENERIC,
        attributes: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        """Scope a span to an ``async with`` block, auto-finishing on exit.

        Finishes :attr:`SpanStatus.ERROR` and re-raises if the body raises,
        otherwise finishes :attr:`SpanStatus.OK`. Either way the span is
        finished, and finishing closes its stack entry. The trailing
        :meth:`_prune` only clears the entry out of this context's tuple when
        the body closed the span from somewhere else; the entry is already
        marked closed by then, so this is housekeeping, not correctness.
        """
        span = self.start_span(name=name, kind=kind, attributes=attributes)
        try:
            yield span
        except BaseException:
            span.finish(SpanStatus.ERROR)
            raise
        else:
            span.finish(SpanStatus.OK)
        finally:
            self._prune()

    def llm_span(
        self, *, name: str = "llm.call", attributes: Mapping[str, Any] | None = None
    ) -> Any:
        """Open an LLM-kind span context manager."""
        return self.span(name=name, kind=SpanKind.LLM, attributes=attributes)

    def tool_span(self, *, name: str, attributes: Mapping[str, Any] | None = None) -> Any:
        """Open a tool-kind span context manager."""
        return self.span(name=name, kind=SpanKind.TOOL, attributes=attributes)

    def retrieval_span(
        self, *, name: str = "retrieval", attributes: Mapping[str, Any] | None = None
    ) -> Any:
        """Open a retrieval-kind span context manager."""
        return self.span(name=name, kind=SpanKind.RETRIEVAL, attributes=attributes)
