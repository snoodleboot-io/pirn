"""Unit tests for the no-op :class:`ObservabilitySink` default."""

from __future__ import annotations

import time

from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind


class TestNoOpSink:
    def test_base_methods_return_none_and_do_nothing(self) -> None:
        sink = ObservabilitySink()
        span = Span(
            name="x",
            kind=SpanKind.GENERIC,
            span_id="s1",
            sink=sink,
            monotonic=time.perf_counter,
        )
        assert sink.on_start(span) is None
        assert sink.on_event(span, "e", {"k": 1}) is None
        assert sink.on_finish(span) is None
