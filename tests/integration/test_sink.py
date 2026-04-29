"""Sink node tests."""

from __future__ import annotations

from typing import ClassVar

from pirn import KnotConfig, Parameter, RunRequest, Sink, Tapestry


class CaptureSink(Sink):
    """A sink that records what it received in a class-level list for testing."""

    received: ClassVar[list] = []

    async def process(self, payload: dict) -> None:
        type(self).received.append(payload)


async def test_sink_consumes_value():
    CaptureSink.received.clear()
    with Tapestry() as t:
        p = Parameter("payload", dict, default={"x": 1})
        CaptureSink(payload=p, _config=KnotConfig(id="sink"))

    result = await t.run(RunRequest())
    assert result.succeeded
    assert CaptureSink.received == [{"x": 1}]


async def test_sink_output_is_none():
    CaptureSink.received.clear()
    with Tapestry() as t:
        p = Parameter("payload", dict, default={"x": 1})
        CaptureSink(payload=p, _config=KnotConfig(id="sink"))
    result = await t.run(RunRequest())
    assert result.outputs["sink"] is None
