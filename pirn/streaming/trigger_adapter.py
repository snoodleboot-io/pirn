"""Adapter: turn a ``StreamingSource`` into a ``Trigger``.

Streaming sources and triggers serve adjacent purposes:

* A ``StreamingSource`` yields values; ``run_stream`` drives one run
  per value, with the value bound to a single named parameter.
* A ``Trigger`` yields full ``RunRequest``s; ``run_forever`` drives
  one run per request.

When you have a streaming source but want to use the
trigger-based machinery (richer per-event ``RunRequest`` shapes,
existing trigger observers), wrap it::

    from pirn.streaming import IterableSource
    from pirn.streaming.trigger_adapter import StreamingSourceTrigger
    from pirn.triggers import run_forever

    source = IterableSource([1, 2, 3], parameter_name="x")
    trigger = StreamingSourceTrigger(source=source)
    await run_forever(trigger, tapestry)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pirn.core.run_request import RunRequest
from pirn.streaming.base import StreamingSource


class StreamingSourceTrigger:
    """Wraps a ``StreamingSource`` as a ``Trigger``.

    Each value from the source becomes a ``RunRequest`` with the
    value bound to ``source.parameter_name``.  Pass a custom
    ``request_builder`` to construct richer requests (e.g., adding
    constants or computing other parameters from the value).
    """

    def __init__(
        self,
        *,
        source: StreamingSource,
        request_builder: Any = None,
    ) -> None:
        self._source = source
        self._builder = request_builder

    @property
    def name(self) -> str:
        return f"StreamingSourceTrigger({self._source.name})"

    async def stream(self) -> AsyncIterator[RunRequest]:
        async for value in self._source.stream():
            if self._builder is not None:
                yield self._builder(value)
            else:
                yield RunRequest(parameters={self._source.parameter_name: value})

    async def close(self) -> None:
        await self._source.close()
