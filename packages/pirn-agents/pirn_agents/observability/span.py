"""``Span`` — one instrumented region of work, reported to an :class:`ObservabilitySink`."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus

if TYPE_CHECKING:
    from pirn_agents.observability.observability_sink import ObservabilitySink


class Span:
    """A single timed, attributed unit of work with start/event/finish callbacks.

    A span is opened by a :class:`~pirn_agents.observability.tracer.Tracer`,
    accrues attributes and events while its wrapped operation runs, and is
    finished exactly once with a terminal :class:`SpanStatus`. Each lifecycle
    transition is reported to the owning
    :class:`~pirn_agents.observability.observability_sink.ObservabilitySink`;
    with the no-op base sink these calls do nothing.

    Attributes
    ----------
    name:
        Human-readable span name (e.g. ``"llm.chat"`` or ``"tool:search"``).
    kind:
        The :class:`SpanKind` classifying the wrapped call site.
    span_id:
        Unique identifier for this span.
    parent_id:
        Enclosing span's id, or ``None`` for a root span.
    attributes:
        Mutable key/value metadata recorded on the span.
    status:
        Terminal disposition; :attr:`SpanStatus.UNSET` until finished.
    events:
        Ordered ``(name, attributes)`` pairs recorded via :meth:`add_event`.
    start_time / end_time:
        Monotonic timestamps; ``end_time`` is ``None`` until finished.
    """

    def __init__(
        self,
        *,
        name: str,
        kind: SpanKind,
        span_id: str,
        sink: ObservabilitySink,
        parent_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.name = name
        self.kind = kind
        self.span_id = span_id
        self.parent_id = parent_id
        self.attributes: dict[str, Any] = dict(attributes or {})
        self.status = SpanStatus.UNSET
        self.events: list[tuple[str, Mapping[str, Any]]] = []
        self._sink = sink
        self._monotonic = monotonic
        self.start_time = monotonic()
        self.end_time: float | None = None

    @property
    def duration(self) -> float | None:
        """Elapsed seconds between start and finish, or ``None`` if unfinished."""
        return None if self.end_time is None else self.end_time - self.start_time

    def set_attribute(self, key: str, value: Any) -> None:
        """Record or overwrite a single attribute on the span."""
        self.attributes[key] = value

    def add_event(self, name: str, **attributes: Any) -> None:
        """Record a named point-in-time event and report it to the sink.

        A sink exception is swallowed so observability can never abort the
        traced operation.
        """
        self.events.append((name, attributes))
        try:
            self._sink.on_event(self, name, attributes)
        except Exception:
            pass

    def finish(self, status: SpanStatus = SpanStatus.OK) -> None:
        """Close the span with ``status`` and report it; idempotent.

        A second call is ignored so a span finished by an error path is not
        re-finished by a surrounding context manager. A sink exception is
        swallowed so observability can never abort the traced operation.
        """
        if self.end_time is not None:
            return
        self.status = status
        self.end_time = self._monotonic()
        try:
            self._sink.on_finish(self)
        except Exception:
            pass
