"""Unit tests for :class:`Span` lifecycle and sink reporting."""

from __future__ import annotations

from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from tests.observability._recording_sink import RecordingSink


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _make(sink: RecordingSink, clock: _Clock) -> Span:
    return Span(
        name="op",
        kind=SpanKind.LLM,
        span_id="s1",
        sink=sink,
        attributes={"model": "stub"},
        monotonic=clock,
    )


class TestSpan:
    def test_duration_none_until_finished(self) -> None:
        span = _make(RecordingSink(), _Clock())
        assert span.duration is None

    def test_finish_sets_status_and_duration(self) -> None:
        sink = RecordingSink()
        clock = _Clock()
        span = _make(sink, clock)
        clock.now = 2.0
        span.finish(SpanStatus.OK)
        assert span.status is SpanStatus.OK
        assert span.duration == 2.0
        assert sink.finished == [span]

    def test_finish_is_idempotent(self) -> None:
        sink = RecordingSink()
        span = _make(sink, _Clock())
        span.finish(SpanStatus.OK)
        span.finish(SpanStatus.ERROR)  # ignored
        assert span.status is SpanStatus.OK
        assert len(sink.finished) == 1

    def test_set_attribute_and_event(self) -> None:
        sink = RecordingSink()
        span = _make(sink, _Clock())
        span.set_attribute("tokens", 12)
        span.add_event("first-token", latency=0.1)
        assert span.attributes["tokens"] == 12
        assert span.events == [("first-token", {"latency": 0.1})]
        assert sink.events == [("s1", "first-token", {"latency": 0.1})]

    def test_sink_exception_swallowed_on_finish(self) -> None:
        class _Boom(RecordingSink):
            def on_finish(self, span: Span) -> None:
                raise RuntimeError("sink down")

        span = _make(_Boom(), _Clock())
        span.finish(SpanStatus.OK)  # must not raise
        assert span.status is SpanStatus.OK
