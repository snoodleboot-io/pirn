"""Unit tests for OpenTelemetryEmitter."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pirn.emitters.otel import OpenTelemetryEmitter


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _make_lineage(outcome: str = "ok") -> MagicMock:
    record = MagicMock()
    record.knot_id = "k1"
    record.run_id = "r1"
    record.knot_class = "MyKnot"
    record.outcome = outcome
    record.dispatcher = "local"
    record.output_hash = "abc"
    record.error_record_id = None
    record.skip_reason = None
    record.started_at = _utcnow()
    record.finished_at = _utcnow()
    return record


def _make_run_result(succeeded: bool = True) -> MagicMock:
    rr = MagicMock()
    rr.run_id = "r1"
    rr.dispatcher = "local"
    rr.succeeded = succeeded
    rr.terminals_requested = ["k1"]
    rr.started_at = _utcnow()
    rr.finished_at = _utcnow()
    return rr


def _make_span() -> MagicMock:
    span = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=False)
    return span


def _make_tracer() -> MagicMock:
    tracer = MagicMock()
    tracer.start_span = MagicMock(return_value=_make_span())
    return tracer


class TestOpenTelemetryEmitterConstruction(unittest.TestCase):
    def test_constructs_with_injected_tracer(self) -> None:
        tracer = MagicMock()
        emitter = OpenTelemetryEmitter(tracer=tracer)
        self.assertIs(emitter._tracer, tracer)

    def test_constructs_without_tracer(self) -> None:
        emitter = OpenTelemetryEmitter()
        self.assertIsNone(emitter._tracer)

    def test_ensure_tracer_raises_without_otel(self) -> None:
        emitter = OpenTelemetryEmitter()
        with patch.dict("sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}):
            import sys
            sys.modules.pop("opentelemetry", None)
            sys.modules.pop("opentelemetry.trace", None)
            # Force lazy import failure
            emitter2 = OpenTelemetryEmitter()
            with self.assertRaises(ImportError):
                emitter2._ensure_tracer()


class TestOpenTelemetryEmitterEvents(unittest.IsolatedAsyncioTestCase):
    async def test_on_status_is_noop(self) -> None:
        emitter = OpenTelemetryEmitter(tracer=_make_tracer())
        await emitter.on_status(MagicMock())  # no exception, no spans

    async def test_on_lineage_creates_span(self) -> None:
        tracer = _make_tracer()
        emitter = OpenTelemetryEmitter(tracer=tracer)
        await emitter.on_lineage(_make_lineage())
        tracer.start_span.assert_called_once()

    async def test_on_run_result_creates_span(self) -> None:
        tracer = _make_tracer()
        emitter = OpenTelemetryEmitter(tracer=tracer)
        await emitter.on_run_result(_make_run_result())
        tracer.start_span.assert_called_once()

    async def test_span_attributes_set_for_lineage(self) -> None:
        span = _make_span()
        tracer = MagicMock()
        tracer.start_span = MagicMock(return_value=span)
        emitter = OpenTelemetryEmitter(tracer=tracer)
        await emitter.on_lineage(_make_lineage(outcome="ok"))
        span.set_attribute.assert_any_call("pirn.run_id", "r1")
        span.set_attribute.assert_any_call("pirn.knot_id", "k1")
        span.end.assert_called_once()

    async def test_err_outcome_sets_error_status(self) -> None:
        try:
            from opentelemetry.trace import Status, StatusCode  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("opentelemetry not installed")
        span = _make_span()
        tracer = MagicMock()
        tracer.start_span = MagicMock(return_value=span)
        emitter = OpenTelemetryEmitter(tracer=tracer)
        await emitter.on_lineage(_make_lineage(outcome="err"))
        span.set_status.assert_called_once()
