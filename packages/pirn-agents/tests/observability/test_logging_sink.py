"""Tests for :class:`LoggingSink` — backend-free span logging via stdlib logging."""

from __future__ import annotations

import logging
import time
import unittest

from pirn_agents.observability.logging_sink import LoggingSink
from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.observability.tracer import Tracer
from pirn_agents.security.secret_redacting_log_filter import SecretRedactingLogFilter


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


class TestLoggingSinkRedactsSecrets(unittest.TestCase):
    """Span attributes are logged verbatim, and nothing constrains what goes in them.

    `SecretRedactingLogFilter` was built and unit-tested but attached to nothing
    (PIR-725). This is the logs surface its own docstring names.
    """

    DSN = "postgresql://admin:hunter2@db.internal/prod"

    def _emit(self, **sink_kwargs: object) -> str:
        logger = logging.getLogger(f"test_redact_{id(self)}_{len(sink_kwargs)}")
        logger.setLevel(logging.DEBUG)
        logger.filters.clear()
        records: list[str] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record.getMessage())

        logger.handlers.clear()
        logger.addHandler(_Capture())
        sink = LoggingSink(logger, **sink_kwargs)  # type: ignore[arg-type]
        span = Span(
            name="op",
            kind=SpanKind.GENERIC,
            span_id="s1",
            sink=sink,
            monotonic=time.perf_counter,
        )
        span.set_attribute("dsn", self.DSN)
        span.finish()
        return "\n".join(records)

    def test_a_secret_in_span_attributes_is_redacted(self) -> None:
        emitted = self._emit()
        assert "hunter2" not in emitted, emitted
        assert "<redacted>" in emitted or "***" in emitted, emitted

    def test_the_span_is_still_logged(self) -> None:
        """Redaction must not swallow the record."""
        assert "span finish" in self._emit()

    def test_opt_out_leaves_the_logger_untouched(self) -> None:
        assert "hunter2" in self._emit(redact_secrets=False)

    def test_attachment_is_idempotent(self) -> None:
        """Several sinks over one logger must not stack filters."""
        logger = logging.getLogger(f"test_idem_{id(self)}")
        logger.filters.clear()
        LoggingSink(logger)
        LoggingSink(logger)
        attached = [f for f in logger.filters if isinstance(f, SecretRedactingLogFilter)]
        assert len(attached) == 1
