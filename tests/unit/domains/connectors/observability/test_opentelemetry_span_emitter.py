"""Unit tests for :class:`OpenTelemetrySpanEmitter`.

Uses an injected stub tracer that mirrors the
``start_as_current_span`` slice of ``opentelemetry.trace``. No real
exporter or collector needed.
"""

from __future__ import annotations

import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pirn.domains.connectors.observability.opentelemetry_config import (
    OpenTelemetryConfig,
)
from pirn.domains.connectors.observability.opentelemetry_span_emitter import (
    OpenTelemetrySpanEmitter,
)

# ──────────────────────────────────────────────────────────── fake tracer


class FakeSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}


class FakeTracer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.entered = 0
        self.exited = 0

    @contextmanager
    def start_as_current_span(self, name: str, attributes: Any = None) -> Iterator[FakeSpan]:
        self.calls.append((name, attributes))
        self.entered += 1
        try:
            yield FakeSpan()
        finally:
            self.exited += 1


# ──────────────────────────────────────────────────────────── construction



class _StandaloneTests(unittest.TestCase):
    def test_construction_requires_config_or_tracer(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or tracer="):
            OpenTelemetrySpanEmitter()
    
    
    def test_sensitive_fields_listed(self) -> None:
        assert OpenTelemetryConfig.sensitive_fields == ()
    
    
# ──────────────────────────────────────────────────────────── emit_span


class TestEmitSpan(unittest.IsolatedAsyncioTestCase):
    async def test_emit_span_starts_and_exits_span(self) -> None:
        fake = FakeTracer()
        emitter = OpenTelemetrySpanEmitter(tracer=fake)

        await emitter.emit_span("op", attributes={"k": "v"})

        assert fake.calls == [("op", {"k": "v"})]
        assert fake.entered == 1
        assert fake.exited == 1

    async def test_emit_span_without_attributes(self) -> None:
        fake = FakeTracer()
        emitter = OpenTelemetrySpanEmitter(tracer=fake)

        await emitter.emit_span("op")

        assert fake.calls == [("op", None)]

    async def test_emit_span_rejects_empty_name(self) -> None:
        emitter = OpenTelemetrySpanEmitter(tracer=FakeTracer())
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await emitter.emit_span("")


# ──────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_is_idempotent(self) -> None:
        emitter = OpenTelemetrySpanEmitter(tracer=FakeTracer())
        await emitter.close()
        await emitter.close()

    async def test_emit_after_close_raises(self) -> None:
        emitter = OpenTelemetrySpanEmitter(tracer=FakeTracer())
        await emitter.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await emitter.emit_span("op")
