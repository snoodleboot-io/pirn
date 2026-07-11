"""``Tracer`` — opens :class:`Span`\\ s around LLM, tool, and retrieval calls."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus


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

    Nesting is tracked on an internal stack so child spans record their
    ``parent_id`` automatically. Sink callbacks are best-effort: any exception a
    sink raises is swallowed so observability can never abort a traced call.
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
        self._stack: list[str] = []

    @property
    def sink(self) -> ObservabilitySink:
        """The sink spans are reported to."""
        return self._sink

    def start_span(
        self,
        *,
        name: str,
        kind: SpanKind = SpanKind.GENERIC,
        attributes: Mapping[str, Any] | None = None,
    ) -> Span:
        """Open and return a span; the caller is responsible for ``finish``.

        The span's ``parent_id`` is taken from the top of the nesting stack, and
        its id is pushed so any span started before it finishes nests beneath it.
        The sink's ``on_start`` is fired (exceptions swallowed) before returning.
        """
        parent_id = self._stack[-1] if self._stack else None
        span = Span(
            name=name,
            kind=kind,
            span_id=self._id_factory(),
            sink=self._sink,
            parent_id=parent_id,
            attributes=attributes,
            monotonic=self._monotonic,
        )
        self._stack.append(span.span_id)
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
        otherwise finishes :attr:`SpanStatus.OK`. The span id is always popped
        from the nesting stack.
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
            if self._stack and self._stack[-1] == span.span_id:
                self._stack.pop()

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
