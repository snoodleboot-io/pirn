"""Emitter tests."""

from __future__ import annotations

import json
import logging

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.lineage import KnotLineage
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.emitters.base import Emitter
from pirn.emitters.kafka import KafkaEmitter
from pirn.emitters.log import LogEmitter
from pirn.emitters.otel import OpenTelemetryEmitter
from pirn.emitters.valkey import ValKeyEmitter
from pirn.emitters.webhook import WebhookEmitter
from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent
from pirn.tapestry import Tapestry

# ============================================================ helpers


def _status_event(**overrides) -> StatusEvent:
    base = dict(run_id="r", knot_id="k", state=KnotState.SUCCEEDED)
    base.update(overrides)
    return StatusEvent(**base)


def _lineage_record(**overrides) -> KnotLineage:
    base = dict(
        run_id="r",
        knot_id="k",
        knot_class="m.K",
        knot_config_hash="sha256:cfg",
        outcome="ok",
        dispatcher="LocalDispatcher",
        output_hash="sha256:out",
    )
    base.update(overrides)
    return KnotLineage(**base)


@knot
async def _double(x: int) -> int:
    return x * 2


# ============================================================ Emitter base


def test_emitter_base_class_has_no_op_defaults():
    """Emitter base class should not require subclasses to override
    every method — defaults are no-ops."""
    e = Emitter()
    # Just check the methods exist and are awaitable (no exception).
    import asyncio

    asyncio.run(e.on_status(_status_event()))
    asyncio.run(e.on_lineage(_lineage_record()))


def test_emitter_name_default_is_class_name():
    class MyEmitter(Emitter):
        pass

    assert MyEmitter().name == "MyEmitter"


# ============================================================ LogEmitter


async def test_log_emitter_records_status(caplog):
    emitter = LogEmitter()
    with caplog.at_level(logging.INFO, logger="pirn"):
        await emitter.on_status(_status_event(state=KnotState.RUNNING))
    assert any("knot k: running" in record.message for record in caplog.records)


async def test_log_emitter_records_lineage(caplog):
    emitter = LogEmitter()
    with caplog.at_level(logging.INFO, logger="pirn"):
        await emitter.on_lineage(_lineage_record())
    assert any("lineage r/k: ok" in r.message for r in caplog.records)


async def test_log_emitter_records_run_result_at_info_when_succeeded(caplog):
    emitter = LogEmitter()

    # Build a real RunResult by running a tapestry.
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest(parameters={"x": 5}))

    with caplog.at_level(logging.INFO, logger="pirn"):
        await emitter.on_run_result(result)

    matches = [r for r in caplog.records if "succeeded" in r.message]
    assert matches
    assert all(r.levelno == logging.INFO for r in matches)


async def test_log_emitter_records_failed_run_at_error(caplog):
    @knot
    async def boom(x: int) -> int:
        raise ValueError("nope")

    emitter = LogEmitter()
    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        boom(x=p, _config=KnotConfig(id="b"))
    result = await t.run(RunRequest())

    with caplog.at_level(logging.ERROR, logger="pirn"):
        await emitter.on_run_result(result)
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records


async def test_log_emitter_with_payload_includes_full_json(caplog):
    emitter = LogEmitter(with_payload=True)
    with caplog.at_level(logging.INFO, logger="pirn"):
        await emitter.on_lineage(_lineage_record())
    record = next(r for r in caplog.records if "lineage r/k: ok" in r.message)
    assert getattr(record, "pirn_payload", None) is not None


# ============================================================ KafkaEmitter


class _FakeKafkaProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes, bytes | None]] = []

    async def send_and_wait(self, topic: str, payload: bytes, key=None) -> None:
        self.sent.append((topic, payload, key))

    async def stop(self) -> None:
        pass


async def test_kafka_emitter_publishes_status():
    producer = _FakeKafkaProducer()
    emitter = KafkaEmitter(producer=producer, topic="pirn-events")
    await emitter.on_status(_status_event())
    assert len(producer.sent) == 1
    topic, payload, key = producer.sent[0]
    assert topic == "pirn-events"
    decoded = json.loads(payload)
    assert decoded["knot_id"] == "k"
    assert key == b"r"


async def test_kafka_emitter_publishes_lineage_and_run_result():
    producer = _FakeKafkaProducer()
    emitter = KafkaEmitter(producer=producer, topic="pirn-events")
    await emitter.on_lineage(_lineage_record())

    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())
    await emitter.on_run_result(result)

    assert len(producer.sent) == 2  # 1 lineage + 1 run_result


async def test_kafka_emitter_per_event_topic_overrides():
    producer = _FakeKafkaProducer()
    emitter = KafkaEmitter(
        producer=producer,
        topic="pirn-events",  # default fallback
        topic_status="pirn-status",
        topic_lineage="pirn-lineage",
    )
    await emitter.on_status(_status_event())
    await emitter.on_lineage(_lineage_record())
    assert producer.sent[0][0] == "pirn-status"
    assert producer.sent[1][0] == "pirn-lineage"


async def test_kafka_emitter_skipped_when_topic_is_none():
    producer = _FakeKafkaProducer()
    emitter = KafkaEmitter(
        producer=producer,
        topic="",  # required to satisfy ctor; we pass falsy then override
        topic_status=None,
    )
    # Patch the default for status to None.  The constructor logic
    # currently uses topic= as fallback, so we override topic_status
    # directly through the public attribute pattern: re-construct.
    emitter._topic_status = None  # type: ignore[attr-defined]
    await emitter.on_status(_status_event())
    assert producer.sent == []


def test_kafka_emitter_requires_producer_or_topic():
    with pytest.raises(TypeError):
        KafkaEmitter()


# ============================================================ ValKeyEmitter


class _FakeValKeyClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))

    async def close(self) -> None:
        pass


async def test_valkey_emitter_publishes_to_default_channels():
    client = _FakeValKeyClient()
    emitter = ValKeyEmitter(client=client)
    await emitter.on_status(_status_event())
    await emitter.on_lineage(_lineage_record())
    channels = [c for c, _ in client.published]
    assert channels == ["pirn:status", "pirn:lineage"]


async def test_valkey_emitter_custom_channels():
    client = _FakeValKeyClient()
    emitter = ValKeyEmitter(
        client=client,
        channel_status="status",
        channel_lineage="lineage",
        channel_result="result",
    )
    await emitter.on_status(_status_event())
    assert client.published[0][0] == "status"


def test_valkey_emitter_requires_client_or_config():
    with pytest.raises(TypeError):
        ValKeyEmitter()


# ============================================================ WebhookEmitter


class _FakeHttpxResponse:
    pass


class _FakeHttpxClient:
    def __init__(self) -> None:
        self.posts: list[tuple[str, str, dict]] = []

    async def post(self, url, content, headers) -> _FakeHttpxResponse:
        self.posts.append((url, content, headers))
        return _FakeHttpxResponse()

    async def aclose(self) -> None:
        pass


async def test_webhook_emitter_posts_status_to_url():
    client = _FakeHttpxClient()
    emitter = WebhookEmitter(
        client=client,
        url_status="https://example.com/status",
    )
    await emitter.on_status(_status_event())
    assert len(client.posts) == 1
    url, content, headers = client.posts[0]
    assert url == "https://example.com/status"
    assert headers["Content-Type"] == "application/json"
    assert json.loads(content)["knot_id"] == "k"


async def test_webhook_emitter_skips_when_url_is_none():
    client = _FakeHttpxClient()
    emitter = WebhookEmitter(client=client)  # all urls None
    await emitter.on_status(_status_event())
    await emitter.on_lineage(_lineage_record())
    assert client.posts == []


async def test_webhook_emitter_independent_urls():
    client = _FakeHttpxClient()
    emitter = WebhookEmitter(
        client=client,
        url_lineage="https://example.com/lineage",
    )
    await emitter.on_status(_status_event())  # no url; skipped
    await emitter.on_lineage(_lineage_record())
    assert len(client.posts) == 1
    assert client.posts[0][0] == "https://example.com/lineage"


# ============================================================ OpenTelemetry


class _FakeOtelSpan:
    def __init__(self, name: str, start_time: int) -> None:
        self.name = name
        self.start_time = start_time
        self.end_time = None
        self.attributes: dict = {}
        self.status = None

    def set_attribute(self, key: str, value) -> None:
        self.attributes[key] = value

    def set_status(self, status) -> None:
        self.status = status

    def end(self, end_time: int) -> None:
        self.end_time = end_time


class _FakeOtelTracer:
    def __init__(self) -> None:
        self.spans: list[_FakeOtelSpan] = []

    def start_span(self, name: str, start_time: int) -> _FakeOtelSpan:
        span = _FakeOtelSpan(name, start_time)
        self.spans.append(span)
        return span


async def test_otel_emitter_creates_lineage_spans():
    tracer = _FakeOtelTracer()
    emitter = OpenTelemetryEmitter(tracer=tracer)
    await emitter.on_lineage(_lineage_record())
    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.name == "knot:k"
    assert span.attributes["pirn.run_id"] == "r"
    assert span.attributes["pirn.knot_id"] == "k"
    assert span.attributes["pirn.outcome"] == "ok"
    assert span.end_time is not None


async def test_otel_emitter_creates_run_span():
    tracer = _FakeOtelTracer()
    emitter = OpenTelemetryEmitter(tracer=tracer)

    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())

    await emitter.on_run_result(result)
    assert len(tracer.spans) == 1
    assert tracer.spans[0].name == f"run:{result.run_id}"


async def test_otel_emitter_no_status_spans():
    """Status events are too noisy for spans; on_status is a no-op."""
    tracer = _FakeOtelTracer()
    emitter = OpenTelemetryEmitter(tracer=tracer)
    await emitter.on_status(_status_event())
    assert tracer.spans == []


async def test_otel_emitter_marks_failed_lineage():
    """A skipped or err lineage record gets the right OTel status."""
    pytest.importorskip("opentelemetry")
    tracer = _FakeOtelTracer()
    emitter = OpenTelemetryEmitter(tracer=tracer)
    await emitter.on_lineage(
        _lineage_record(outcome="err", error_record_id="exc-1", output_hash=None)
    )
    assert tracer.spans[0].status is not None


# ============================================================ Engine wiring


async def test_emitters_receive_events_via_tapestry():
    """Wiring: emitters passed to a Tapestry receive on_status,
    on_lineage, and on_run_result during a run."""

    class CapturingEmitter(Emitter):
        def __init__(self) -> None:
            self.statuses: list[StatusEvent] = []
            self.lineages: list[KnotLineage] = []
            self.results: list[RunResult] = []

        async def on_status(self, event: StatusEvent) -> None:
            self.statuses.append(event)

        async def on_lineage(self, record: KnotLineage) -> None:
            self.lineages.append(record)

        async def on_run_result(self, result: RunResult) -> None:
            self.results.append(result)

    emitter = CapturingEmitter()
    with Tapestry(emitters=[emitter]) as t:
        p = Parameter("x", int, default=5, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())

    # Give scheduled status tasks a moment to drain.
    import asyncio

    await asyncio.sleep(0.05)

    assert emitter.results == [result]
    # Two knots x at least one transition each = at least 2 status events.
    assert len(emitter.statuses) >= 2
    # Lineage records: one per knot.
    assert len(emitter.lineages) == 2


async def test_emitter_failure_does_not_break_run():
    """A broken emitter must not bring down the run."""

    class BrokenEmitter(Emitter):
        async def on_status(self, event: StatusEvent) -> None:
            raise RuntimeError("status broken")

        async def on_lineage(self, record: KnotLineage) -> None:
            raise RuntimeError("lineage broken")

        async def on_run_result(self, result: RunResult) -> None:
            raise RuntimeError("result broken")

    with Tapestry(emitters=[BrokenEmitter()]) as t:
        p = Parameter("x", int, default=5, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["d"] == 10


async def test_per_run_emitter_override():
    """Passing emitters=[...] to run() overrides the tapestry default."""

    class C(Emitter):
        def __init__(self, label: str):
            self.label = label
            self.results: list[RunResult] = []

        async def on_run_result(self, result: RunResult) -> None:
            self.results.append(result)

    default = C("default")
    override = C("override")
    with Tapestry(emitters=[default]) as t:
        p = Parameter("x", int, default=5, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    await t.run(RunRequest(), emitters=[override])
    assert override.results
    assert default.results == []
