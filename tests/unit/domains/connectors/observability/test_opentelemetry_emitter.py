"""Unit tests for :class:`OpenTelemetryEmitter`.

Uses an injected stub tracer that mirrors the
``start_as_current_span`` slice of ``opentelemetry.trace``. No real
exporter or collector needed.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from pirn.domains.connectors.observability.opentelemetry_config import (
    OpenTelemetryConfig,
)
from pirn.domains.connectors.observability.opentelemetry_emitter import (
    OpenTelemetryEmitter,
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
    def start_as_current_span(
        self, name: str, attributes: Any = None
    ) -> Iterator[FakeSpan]:
        self.calls.append((name, attributes))
        self.entered += 1
        try:
            yield FakeSpan()
        finally:
            self.exited += 1


# ──────────────────────────────────────────────────────────── construction


def test_construction_requires_config_or_tracer() -> None:
    with pytest.raises(TypeError, match="config= or tracer="):
        OpenTelemetryEmitter()


def test_sensitive_fields_listed() -> None:
    assert OpenTelemetryConfig.sensitive_fields == ()


# ──────────────────────────────────────────────────────────── emit_span


@pytest.mark.asyncio
class TestEmitSpan:
    async def test_emit_span_starts_and_exits_span(self) -> None:
        fake = FakeTracer()
        emitter = OpenTelemetryEmitter(tracer=fake)

        await emitter.emit_span("op", attributes={"k": "v"})

        assert fake.calls == [("op", {"k": "v"})]
        assert fake.entered == 1
        assert fake.exited == 1

    async def test_emit_span_without_attributes(self) -> None:
        fake = FakeTracer()
        emitter = OpenTelemetryEmitter(tracer=fake)

        await emitter.emit_span("op")

        assert fake.calls == [("op", None)]

    async def test_emit_span_rejects_empty_name(self) -> None:
        emitter = OpenTelemetryEmitter(tracer=FakeTracer())
        with pytest.raises(ValueError, match="non-empty"):
            await emitter.emit_span("")


# ──────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_is_idempotent(self) -> None:
        emitter = OpenTelemetryEmitter(tracer=FakeTracer())
        await emitter.close()
        await emitter.close()

    async def test_emit_after_close_raises(self) -> None:
        emitter = OpenTelemetryEmitter(tracer=FakeTracer())
        await emitter.close()
        with pytest.raises(RuntimeError, match="closed"):
            await emitter.emit_span("op")
