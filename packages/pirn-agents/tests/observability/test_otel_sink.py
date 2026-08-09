"""Tests for :class:`OtelSink` — lazy backend guard, span mapping, redaction.

``opentelemetry`` is not installed in the base env, so construction must raise a
friendly :class:`ImportError`. The mapping behaviour is exercised against a
minimal fake ``opentelemetry.trace`` module injected into ``sys.modules``, so no
real backend is required.

:class:`TestAttributeRedaction` covers PIR-789: attributes are exported to a
third-party collector, so they go through the same
:class:`~pirn_agents.security.secret_leak_scanner.SecretLeakScanner` machinery
PIR-725 wired into :class:`~pirn_agents.observability.logging_sink.LoggingSink`.
"""

from __future__ import annotations

import sys
import time
import types
from typing import Any
from unittest import mock

import pytest

from pirn_agents.observability.span import Span
from pirn_agents.observability.span_kind import SpanKind
from pirn_agents.observability.span_status import SpanStatus
from pirn_agents.security.secret_leak_scanner import SecretLeakScanner
from pirn_agents.security.secret_redactor import SecretRedactor


class TestLazyBackendGuard:
    def test_missing_backend_raises_friendly(self) -> None:
        # opentelemetry may be installed (CI installs the [otel] extra); force it
        # absent so the friendly install-error path is deterministic.
        from pirn_agents.observability.otel_sink import OtelSink

        with mock.patch.dict(sys.modules, {"opentelemetry.trace": None}):
            with pytest.raises(ImportError, match=r"pirn-agents\[otel\]"):
                OtelSink()


class _FakeOtelSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}
        self.status: Any = None
        self.ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Any) -> None:
        self.status = status

    def end(self) -> None:
        self.ended = True


class _FakeOtelTracer:
    def __init__(self) -> None:
        self.spans: list[_FakeOtelSpan] = []

    def start_span(self, name: str) -> _FakeOtelSpan:
        span = _FakeOtelSpan()
        span.attributes["__name__"] = name
        self.spans.append(span)
        return span


@pytest.fixture
def fake_otel(monkeypatch: pytest.MonkeyPatch) -> _FakeOtelTracer:
    """Inject a minimal fake ``opentelemetry.trace`` module."""
    tracer = _FakeOtelTracer()
    trace_mod = types.ModuleType("opentelemetry.trace")
    trace_mod.get_tracer = lambda _name: tracer  # type: ignore[attr-defined]
    trace_mod.Status = lambda code: ("status", code)  # type: ignore[attr-defined]
    trace_mod.StatusCode = types.SimpleNamespace(ERROR="ERROR")  # type: ignore[attr-defined]
    pkg = types.ModuleType("opentelemetry")
    monkeypatch.setitem(sys.modules, "opentelemetry", pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace_mod)
    return tracer


class TestSpanMapping:
    def test_finish_emits_mapped_otel_span(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink()
        span = Span(
            name="llm.chat",
            kind=SpanKind.LLM,
            span_id="s1",
            sink=sink,
            attributes={"model": "stub", "obj": object()},
            monotonic=time.perf_counter,
        )
        span.finish(SpanStatus.OK)
        assert len(fake_otel.spans) == 1
        otel_span = fake_otel.spans[0]
        assert otel_span.ended is True
        assert otel_span.attributes["pirn.span.kind"] == "llm"
        assert otel_span.attributes["pirn.span.status"] == "ok"
        assert otel_span.attributes["model"] == "stub"
        # Non-primitive attribute stringified rather than dropped.
        assert isinstance(otel_span.attributes["obj"], str)

    def test_error_span_sets_error_status(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink()
        span = Span(name="tool", kind=SpanKind.TOOL, span_id="s2", sink=sink)
        span.finish(SpanStatus.ERROR)
        assert fake_otel.spans[0].status == ("status", "ERROR")


class _ConnectionHandle:
    """A non-primitive attribute value whose ``repr`` carries a live DSN.

    The realistic shape: nobody puts a password in a span attribute on purpose,
    they attach the client object and the sink stringifies it.
    """

    def __repr__(self) -> str:
        return "_ConnectionHandle(dsn='postgresql://admin:hunter2@db.internal/prod')"


class _ClientConfig:
    """A non-primitive attribute value whose ``repr`` carries an API key."""

    def __repr__(self) -> str:
        return "_ClientConfig(api_key='k-live-4f9a2c7e18b3', region='eu-west-1')"


class TestAttributeRedaction:
    def test_dsn_in_a_string_attribute_is_redacted_at_export(
        self, fake_otel: _FakeOtelTracer
    ) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink()
        span = Span(
            name="db.query",
            kind=SpanKind.TOOL,
            span_id="s3",
            sink=sink,
            attributes={"db.url": "postgresql://admin:hunter2@db.internal/prod"},
        )
        span.finish(SpanStatus.OK)
        exported = fake_otel.spans[0].attributes["db.url"]
        assert "hunter2" not in exported
        assert "<redacted>" in exported
        # Only the credential goes — the host stays, or the trace is useless.
        assert "db.internal" in exported

    def test_secret_bearing_key_name_is_blanked(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink()
        span = Span(
            name="tool:fetch",
            kind=SpanKind.TOOL,
            span_id="s4",
            sink=sink,
            attributes={"authorization": "Bearer abcdef0123456789"},
        )
        span.finish(SpanStatus.OK)
        assert fake_otel.spans[0].attributes["authorization"] == "<redacted>"

    def test_repr_of_a_non_primitive_is_redacted(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink()
        span = Span(
            name="db.query",
            kind=SpanKind.TOOL,
            span_id="s5",
            sink=sink,
            attributes={"conn": _ConnectionHandle(), "config": _ClientConfig()},
        )
        span.finish(SpanStatus.OK)
        exported = fake_otel.spans[0].attributes
        assert "hunter2" not in exported["conn"]
        assert "k-live-4f9a2c7e18b3" not in exported["config"]
        assert "eu-west-1" in exported["config"]

    def test_nested_container_attribute_is_redacted(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink()
        span = Span(
            name="tool:fetch",
            kind=SpanKind.TOOL,
            span_id="s6",
            sink=sink,
            attributes={"args": {"endpoint": "https://api.example.com/v1?api_key=abc123def456"}},
        )
        span.finish(SpanStatus.OK)
        assert "abc123def456" not in fake_otel.spans[0].attributes["args"]

    def test_benign_attributes_survive_untouched(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink()
        span = Span(
            name="llm.chat",
            kind=SpanKind.LLM,
            span_id="s7",
            sink=sink,
            attributes={"model": "stub", "tokens": 42, "stream": True, "temperature": 0.5},
        )
        span.finish(SpanStatus.OK)
        exported = fake_otel.spans[0].attributes
        assert exported["model"] == "stub"
        assert exported["tokens"] == 42
        assert exported["stream"] is True
        assert exported["temperature"] == 0.5

    def test_redaction_can_be_opted_out_of(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        sink = OtelSink(redact_secrets=False)
        span = Span(
            name="db.query",
            kind=SpanKind.TOOL,
            span_id="s8",
            sink=sink,
            attributes={"db.url": "postgresql://admin:hunter2@db.internal/prod"},
        )
        span.finish(SpanStatus.OK)
        assert "hunter2" in fake_otel.spans[0].attributes["db.url"]

    def test_an_injected_redactor_is_used(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        scanner = SecretLeakScanner(extra_patterns=(("employee_id", r"\bEMP-[0-9]{4}\b"),))
        sink = OtelSink(redactor=SecretRedactor(scanner=scanner))
        span = Span(
            name="tool:lookup",
            kind=SpanKind.TOOL,
            span_id="s9",
            sink=sink,
            attributes={"subject": "EMP-8821"},
        )
        span.finish(SpanStatus.OK)
        assert fake_otel.spans[0].attributes["subject"] == "<redacted>"

    def test_a_non_redactor_is_rejected(self, fake_otel: _FakeOtelTracer) -> None:
        from pirn_agents.observability.otel_sink import OtelSink

        with pytest.raises(TypeError, match="SecretRedactor"):
            OtelSink(redactor=object())  # type: ignore[arg-type]
