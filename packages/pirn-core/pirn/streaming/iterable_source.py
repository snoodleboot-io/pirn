"""IterableSource — wraps any async iterable into a StreamingSource."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable
from typing import Any

from pirn.streaming.streaming_source import StreamingSource


class IterableSource(StreamingSource):
    """Streaming source over an arbitrary iterable (sync or async).

    Useful for tests and for adapting any data source you can express
    as an iterator.  For production use, prefer the dedicated source
    types (Kafka, file tail, etc.) which handle their backends'
    lifecycles correctly.
    """

    def __init__(
        self,
        iterable: Iterable[Any] | AsyncIterable[Any],
        *,
        parameter_name: str,
        name: str = "IterableSource",
    ) -> None:
        self._iterable = iterable
        self._parameter_name = parameter_name
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def parameter_name(self) -> str:
        return self._parameter_name

    async def stream(self) -> AsyncIterator[Any]:
        if isinstance(self._iterable, AsyncIterable):
            async for v in self._iterable:
                yield v
        else:
            for v in self._iterable:
                yield v

    async def close(self) -> None:
        pass
