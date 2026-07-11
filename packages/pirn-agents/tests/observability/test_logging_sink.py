"""Tests for :class:`LoggingSink` — backend-free span logging via stdlib logging."""

from __future__ import annotations

import logging
import time

from pirn_agents.observability.logging_sink import LoggingSink
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.observability.tracer import Tracer


class TestLoggingSink:
    async def test_finish_logs_at_configured_level(self, caplog) -> None:
        logger = logging.getLogger("pirn_agents.test.logging_sink")
        sink = LoggingSink(logger, level=logging.INFO)
        tracer = Tracer(sink)
        with caplog.at_level(logging.INFO, logger=logger.name):
            async with tracer.llm_span(name="llm.chat") as span:
                span.set_attribute("model", "stub")
        assert span.status is SpanStatus.OK
        assert any("span finish" in rec.message for rec in caplog.records)

    def test_event_logged_at_debug(self, caplog) -> None:
        logger = logging.getLogger("pirn_agents.test.logging_sink.event")
        sink = LoggingSink(logger)
        span = Span(
            name="op",
            kind=SpanKind.GENERIC,
            span_id="s1",
            sink=sink,
            monotonic=time.perf_counter,
        )
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            span.add_event("first-token", latency=0.1)
        assert any("span event" in rec.message for rec in caplog.records)
