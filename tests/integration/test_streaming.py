"""Streaming source tests."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from pirn import KnotConfig, Parameter, Tapestry, knot
from pirn.streaming import (
    FileTailSource,
    IterableSource,
    KafkaStreamingSource,
    StreamingSource,
    run_stream,
)

# ============================================================ IterableSource


async def test_iterable_source_yields_sync_iterable():
    source = IterableSource([1, 2, 3], parameter_name="x")
    values = []
    async for v in source.stream():
        values.append(v)
    assert values == [1, 2, 3]


async def test_iterable_source_yields_async_iterable():
    async def agen():
        for v in ["a", "b", "c"]:
            yield v

    source = IterableSource(agen(), parameter_name="x")
    values = [v async for v in source.stream()]
    assert values == ["a", "b", "c"]


def test_iterable_source_protocol():
    """An IterableSource should satisfy the StreamingSource protocol."""
    source = IterableSource([1], parameter_name="x")
    assert isinstance(source, StreamingSource)


def test_iterable_source_name_and_parameter():
    source = IterableSource([1], parameter_name="my_param", name="my_source")
    assert source.name == "my_source"
    assert source.parameter_name == "my_param"


# ============================================================ run_stream


@knot
async def _double(x: int) -> int:
    return x * 2


async def test_run_stream_drives_tapestry_per_value():
    """The driver runs the tapestry once per value yielded by the
    source."""
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    source = IterableSource([1, 2, 3, 4], parameter_name="x")
    captured = []

    async def on_result(value, result):
        captured.append((value, result.outputs["d"]))

    await run_stream(source, t, on_result=on_result)

    assert captured == [(1, 2), (2, 4), (3, 6), (4, 8)]


async def test_run_stream_extra_parameters_merged_with_source_value():
    """Constants for the run merged into each tick's parameters."""

    @knot
    async def add_const(x: int, const: int) -> int:
        return x + const

    with Tapestry() as t:
        p_x = Parameter("x", int, _config=KnotConfig(id="x"))
        p_c = Parameter("const", int, _config=KnotConfig(id="c"))
        add_const(x=p_x, const=p_c, _config=KnotConfig(id="r"))

    source = IterableSource([1, 2, 3], parameter_name="x")
    sums = []

    async def on_result(value, result):
        sums.append(result.outputs["r"])

    await run_stream(
        source,
        t,
        on_result=on_result,
        extra_parameters={"const": 100},
    )

    assert sums == [101, 102, 103]


async def test_run_stream_on_error_called_for_engine_errors():
    """Engine-level errors (not knot errors) route through on_error."""
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    # Source that yields one valid value and then raises.
    async def faulty_source_iter():
        yield 1
        raise RuntimeError("source died")

    source = IterableSource(faulty_source_iter(), parameter_name="x")
    successes = []

    async def on_result(value, result):
        successes.append(result.outputs["d"])

    # Source's exception isn't an engine error — it propagates from
    # the stream itself, which run_stream's try/finally catches.
    with pytest.raises(RuntimeError, match="source died"):
        await run_stream(source, t, on_result=on_result)

    assert successes == [2]  # the one tick that got through


# ============================================================ FileTailSource


async def test_file_tail_yields_new_lines():
    """Append lines to a file and verify the source yields them."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "log.txt"
        path.write_text("")

        source = FileTailSource(
            path,
            parameter_name="line",
            poll_seconds=0.01,
        )

        captured = []

        async def consume():
            async for line in source.stream():
                captured.append(line)
                if len(captured) == 3:
                    await source.close()

        # Start the consumer.
        consumer = asyncio.create_task(consume())
        # Give it a moment to seek to end.
        await asyncio.sleep(0.05)
        # Append three lines.
        with path.open("a") as f:
            f.write("first\n")
            f.write("second\n")
            f.write("third\n")
        await asyncio.wait_for(consumer, timeout=2.0)
        assert captured == ["first", "second", "third"]


async def test_file_tail_from_start_replays_existing_content():
    """from_start=True yields content that was already in the file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "log.txt"
        path.write_text("alpha\nbeta\n")

        source = FileTailSource(
            path,
            parameter_name="line",
            from_start=True,
            poll_seconds=0.01,
        )

        captured = []

        async def consume():
            async for line in source.stream():
                captured.append(line)
                if len(captured) == 2:
                    await source.close()

        await asyncio.wait_for(consume(), timeout=2.0)
        assert captured == ["alpha", "beta"]


# ============================================================ Kafka


class _FakeKafkaMessage:
    def __init__(self, value: bytes) -> None:
        self.value = value


class _FakeKafkaConsumer:
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


async def test_kafka_streaming_source_yields_decoded_messages():
    """Default decoder treats value as JSON; verify that pipeline."""
    consumer = _FakeKafkaConsumer([
        _FakeKafkaMessage(b"42"),
        _FakeKafkaMessage(b'{"x": 1}'),
        _FakeKafkaMessage(b'"hello"'),
    ])
    source = KafkaStreamingSource(
        consumer=consumer,
        parameter_name="payload",
    )
    values = [v async for v in source.stream()]
    assert values == [42, {"x": 1}, "hello"]


async def test_kafka_streaming_source_custom_decoder():
    consumer = _FakeKafkaConsumer([
        _FakeKafkaMessage(b"foo"),
        _FakeKafkaMessage(b"bar"),
    ])

    def decode(msg: Any) -> str:
        return msg.value.decode().upper()

    source = KafkaStreamingSource(
        consumer=consumer,
        parameter_name="x",
        decoder=decode,
    )
    values = [v async for v in source.stream()]
    assert values == ["FOO", "BAR"]


def test_kafka_streaming_source_requires_consumer_or_topic():
    with pytest.raises(TypeError):
        KafkaStreamingSource(parameter_name="x")
