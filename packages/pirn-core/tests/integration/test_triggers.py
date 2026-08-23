"""Trigger tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import time
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn.triggers.base import run_forever
from pirn.triggers.cron import CronTrigger
from pirn.triggers.http import WebhookTrigger
from pirn.triggers.kafka import KafkaTrigger
from pirn.triggers.valkey import ValKeyTrigger

# ============================================================ CronTrigger


async def test_cron_trigger_every_seconds_emits_max_runs():
    """Bounded run via max_runs so the test doesn't hang."""
    trigger = CronTrigger(every_seconds=0.01, max_runs=3)
    requests = []
    async for request in trigger.stream():
        requests.append(request)
    assert len(requests) == 3


async def test_cron_trigger_parameters_factory_called_per_emission():
    """Factory builds a fresh parameters dict per request."""
    counter = {"n": 0}

    def factory():
        counter["n"] += 1
        return {"index": counter["n"]}

    trigger = CronTrigger(
        every_seconds=0.01,
        parameters_factory=factory,
        max_runs=2,
    )
    requests = []
    async for r in trigger.stream():
        requests.append(r)
    assert requests[0].parameters == {"index": 1}
    assert requests[1].parameters == {"index": 2}


def test_cron_trigger_requires_either_mode():
    with pytest.raises(TypeError, match=r"every_seconds=.*at_times="):
        CronTrigger()


def test_cron_trigger_rejects_both_modes():
    with pytest.raises(TypeError, match="not both"):
        CronTrigger(every_seconds=10, at_times=[time(9)])


def test_cron_trigger_name():
    assert CronTrigger(every_seconds=10).name == "CronTrigger"


# ============================================================ run_forever


@knot
async def _record(x: int) -> int:
    return x * 2


async def test_run_forever_drives_tapestry_per_request():
    """The runtime helper consumes requests from a trigger and runs
    the tapestry for each."""
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _record(x=p, _config=KnotConfig(id="r"))

    trigger = CronTrigger(
        every_seconds=0.001,
        parameters_factory=lambda: {"x": 7},
        max_runs=3,
    )

    captured = []

    async def on_result(req, res):
        captured.append((req, res))

    await run_forever(trigger, t, on_result=on_result)

    assert len(captured) == 3
    for _, res in captured:
        assert res.outputs["r"] == 14


async def test_run_forever_swallows_run_errors_via_on_error():
    """A failing run is reported via on_error rather than crashing the
    driver."""

    @knot
    async def boom(x: int) -> int:
        raise ValueError("boom")

    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        boom(x=p, _config=KnotConfig(id="b"))

    trigger = CronTrigger(
        every_seconds=0.001,
        parameters_factory=lambda: {"x": 1},
        max_runs=2,
    )

    errors = []

    async def on_error(req, exc):
        errors.append((req, exc))

    # Note: knot exceptions are caught by the engine into Err, so the
    # run completes successfully (it just has exceptions in the
    # result).  on_error is for *engine-level* errors.  Verify on_result
    # still fires for failed runs.
    successes = []

    async def on_result(req, res):
        successes.append(res)

    await run_forever(trigger, t, on_result=on_result, on_error=on_error)
    assert len(successes) == 2
    assert all(not r.succeeded for r in successes)


# ============================================================ KafkaTrigger


class _FakeKafkaMessage:
    def __init__(self, value: bytes) -> None:
        self.value = value


class _FakeKafkaConsumer:
    """Async-iterable fake consumer."""

    def __init__(self, messages: list[_FakeKafkaMessage]) -> None:
        self._messages = messages
        self._index = 0

    def __aiter__(self) -> AsyncIterator[_FakeKafkaMessage]:
        return self

    async def __anext__(self) -> _FakeKafkaMessage:
        if self._index >= len(self._messages):
            raise StopAsyncIteration
        msg = self._messages[self._index]
        self._index += 1
        return msg

    async def stop(self) -> None:
        pass


async def test_kafka_trigger_decodes_json_message_to_request():
    consumer = _FakeKafkaConsumer(
        [
            _FakeKafkaMessage(b'{"x": 5}'),
            _FakeKafkaMessage(b'{"x": 10}'),
        ]
    )
    trigger = KafkaTrigger(consumer=consumer)
    requests = []
    async for r in trigger.stream():
        requests.append(r)
    assert [r.parameters for r in requests] == [{"x": 5}, {"x": 10}]


async def test_kafka_trigger_rejects_non_object_payload():
    consumer = _FakeKafkaConsumer([_FakeKafkaMessage(b"[1, 2, 3]")])
    trigger = KafkaTrigger(consumer=consumer)
    with pytest.raises(TypeError, match="JSON object"):
        async for _ in trigger.stream():
            pass


async def test_kafka_trigger_custom_request_builder():
    """The builder hook can read message keys, headers, etc."""

    def builder(msg: Any) -> RunRequest:
        # Decode value as comma-separated x,y.
        x, y = msg.value.decode().split(",")
        return RunRequest(parameters={"x": int(x), "y": int(y)})

    consumer = _FakeKafkaConsumer([_FakeKafkaMessage(b"3,4")])
    trigger = KafkaTrigger(consumer=consumer, request_builder=builder)
    requests = [r async for r in trigger.stream()]
    assert requests[0].parameters == {"x": 3, "y": 4}


def test_kafka_trigger_requires_consumer_or_topic():
    with pytest.raises(TypeError):
        KafkaTrigger()


# ============================================================ ValKeyTrigger


class _FakeValKeyMessage:
    def __init__(self, message: bytes) -> None:
        self.message = message


class _FakeValKeyClient:
    def __init__(self, messages: list[_FakeValKeyMessage]) -> None:
        self._messages = messages
        self._index = 0

    async def get_pubsub_message(self) -> _FakeValKeyMessage | None:
        if self._index >= len(self._messages):
            # Return None to signal no message; the trigger loops until
            # closed.  Tests close after collecting messages.
            return None
        msg = self._messages[self._index]
        self._index += 1
        return msg

    async def close(self) -> None:
        pass


async def test_valkey_trigger_decodes_messages_until_closed():
    client = _FakeValKeyClient(
        [
            _FakeValKeyMessage(b'{"a": 1}'),
            _FakeValKeyMessage(b'{"a": 2}'),
        ]
    )
    trigger = ValKeyTrigger(client=client)

    captured = []

    async def consume():
        async for r in trigger.stream():
            captured.append(r)
            if len(captured) == 2:
                await trigger.close()

    await asyncio.wait_for(consume(), timeout=2.0)
    assert [r.parameters for r in captured] == [{"a": 1}, {"a": 2}]


# ============================================================ WebhookTrigger


async def test_webhook_trigger_submit_method_enqueues_request():
    """Programmatic submission (without HTTP) drives the same queue."""
    trigger = WebhookTrigger()
    captured = []

    async def consume():
        async for r in trigger.stream():
            captured.append(r)
            if len(captured) == 2:
                await trigger.close()

    consumer = asyncio.create_task(consume())
    await trigger.submit(RunRequest(parameters={"a": 1}))
    await trigger.submit(RunRequest(parameters={"a": 2}))
    await asyncio.wait_for(consumer, timeout=2.0)

    assert [r.parameters for r in captured] == [{"a": 1}, {"a": 2}]


async def test_webhook_trigger_close_unblocks_stream():
    """Closing the trigger ends the stream cleanly."""
    trigger = WebhookTrigger()

    async def consume():
        async for _ in trigger.stream():
            pass

    consumer = asyncio.create_task(consume())
    # Give the consumer a moment to enter the await.
    await asyncio.sleep(0.01)
    await trigger.close()
    await asyncio.wait_for(consumer, timeout=2.0)
