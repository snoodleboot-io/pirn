"""Tests for :class:`OtelSink` — lazy backend guard and span mapping.

``opentelemetry`` is not installed in the base env, so construction must raise a
friendly :class:`ImportError`. The mapping behaviour is exercised against a
minimal fake ``opentelemetry.trace`` module injected into ``sys.modules``, so no
real backend is required.
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
