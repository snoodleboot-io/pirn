"""A test-only :class:`ObservabilitySink` that records every callback."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.span import Span


class RecordingSink(ObservabilitySink):
    """Captures started, finished, and event spans for assertions."""

    def __init__(self) -> None:
        self.started: list[Span] = []
        self.finished: list[Span] = []
        self.events: list[tuple[str, str, Mapping[str, Any]]] = []

    def on_start(self, span: Span) -> None:
        self.started.append(span)

    def on_event(self, span: Span, name: str, attributes: Mapping[str, Any]) -> None:
        self.events.append((span.span_id, name, dict(attributes)))

    def on_finish(self, span: Span) -> None:
        self.finished.append(span)
