"""Real-backend tests for Kafka trigger, emitter, and streaming source.

Gated by ``pytest.mark.needs_kafka``.  Set ``PIRN_TEST_KAFKA_URL``
(e.g. ``localhost:9092``) to run; tests skip silently when it is absent.

Each test uses a unique topic name and consumer group ID to prevent
offset state leaking between runs.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.needs_kafka


# ------------------------------------------------------------- helpers


def _bootstrap() -> str:
    url = os.environ.get("PIRN_TEST_KAFKA_URL")
    if not url:
        pytest.skip("PIRN_TEST_KAFKA_URL not set")
    try:
        import aiokafka  # noqa: F401
    except ImportError:
        pytest.skip("aiokafka not installed")
    return url


def _unique_topic() -> str:
    return f"pirn-test-{uuid.uuid4()}"


def _unique_group() -> str:
    return f"pirn-test-{uuid.uuid4()}"


async def _produce(bootstrap: str, topic: str, messages: list[dict]) -> None:
    """Publish JSON messages to a topic and flush."""
    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(bootstrap_servers=bootstrap)
    await producer.start()
    try:
        for msg in messages:
            await producer.send_and_wait(topic, json.dumps(msg).encode("utf-8"))
    finally:
        await producer.stop()


async def _consume_n(bootstrap: str, topic: str, group: str, n: int) -> list[bytes]:
    """Consume exactly n messages from the beginning of a topic."""
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=group,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        messages = []
        async for msg in consumer:
            messages.append(msg.value)
            if len(messages) >= n:
                break
        return messages
    finally:
        await consumer.stop()


# ------------------------------------------------------------- trigger tests


async def test_kafka_trigger_consumes_real_messages():
    """Produce 3 messages; KafkaTrigger must yield 3 RunRequests."""
    from aiokafka import AIOKafkaConsumer
    from pirn.triggers.kafka import KafkaTrigger

    bootstrap = _bootstrap()
    topic = _unique_topic()
    group = _unique_group()

    payloads = [{"x": 1}, {"x": 2}, {"x": 3}]
    await _produce(bootstrap, topic, payloads)

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=group,
        auto_offset_reset="earliest",
    )
    await consumer.start()

    trigger = KafkaTrigger(consumer=consumer)
    requests = []
    try:
        async for req in trigger.stream():
            requests.append(req)
            if len(requests) >= 3:
                break
    finally:
        await trigger.close()

    assert len(requests) == 3
    assert [r.parameters["x"] for r in requests] == [1, 2, 3]


# ------------------------------------------------------------- emitter tests


async def test_kafka_emitter_publishes_status_event_to_topic():
    """Emit a status event; consume from the topic and verify the JSON."""
    from pirn.emitters.kafka import KafkaEmitter
    from pirn.managers.knot_state import KnotState
    from pirn.managers.status_event import StatusEvent

    bootstrap = _bootstrap()
    topic = _unique_topic()
    group = _unique_group()

    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(bootstrap_servers=bootstrap)
    await producer.start()
    emitter = KafkaEmitter(producer=producer, topic=topic)

    event = StatusEvent(
        run_id="run-kafka-test",
        knot_id="k",
        state=KnotState.RUNNING,
    )
    await emitter.on_status(event)
    await emitter.close()

    raw_messages = await _consume_n(bootstrap, topic, group, 1)
    assert len(raw_messages) == 1
    decoded = json.loads(raw_messages[0])
    assert decoded["run_id"] == "run-kafka-test"
    assert decoded["knot_id"] == "k"


# ------------------------------------------------------------- streaming tests


@knot
async def _echo(x: int) -> int:
    return x


async def test_kafka_streaming_source_drives_run_per_message():
    """Produce 5 messages; run_stream must complete 5 runs with correct outputs."""
    from aiokafka import AIOKafkaConsumer
    from pirn.streaming.base import run_stream
    from pirn.streaming.kafka import KafkaStreamingSource

    bootstrap = _bootstrap()
    topic = _unique_topic()
    group = _unique_group()

    # Produce 5 integer values (the source decodes JSON, so send plain ints).
    payloads_raw = [str(i).encode() for i in range(5)]
    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(bootstrap_servers=bootstrap)
    await producer.start()
    for payload in payloads_raw:
        await producer.send_and_wait(topic, payload)
    await producer.stop()

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=group,
        auto_offset_reset="earliest",
    )
    await consumer.start()

    source = KafkaStreamingSource(consumer=consumer, parameter_name="x")

    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _echo(x=p, _config=KnotConfig(id="out"))

    results = []

    async def collect(value, result):
        results.append(result)
        if len(results) >= 5:
            raise asyncio.CancelledError

    try:
        await run_stream(source, t, on_result=collect)
    except asyncio.CancelledError:
        pass

    assert len(results) == 5
    assert all(r.succeeded for r in results)
    outputs = sorted(r.outputs["out"] for r in results)
    assert outputs == list(range(5))
