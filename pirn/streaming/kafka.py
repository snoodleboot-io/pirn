"""Kafka streaming source — yield Kafka messages as values for a run."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from pirn.streaming.base import StreamingSource


class KafkaStreamingSource(StreamingSource):
    """Streams messages from a Kafka topic as values for a long-running run.

    Each message becomes one value; downstream knots see it bound to
    ``parameter_name``.  The default decoder treats the message value
    as a JSON-encoded scalar/object; override via ``decoder`` for
    custom payloads (Avro, Protobuf, raw bytes, etc.).

    Construction:

    * ``KafkaStreamingSource(consumer=..., parameter_name=...)`` —
      inject an existing aiokafka consumer.
    * ``KafkaStreamingSource(topic=..., bootstrap_servers=...,
      parameter_name=...)`` — build a consumer lazily.
    """

    def __init__(
        self,
        *,
        parameter_name: str,
        consumer: Any = None,
        topic: str | None = None,
        bootstrap_servers: str | None = None,
        group_id: str = "pirn-stream",
        decoder: Any = None,
        name: str = "KafkaStreamingSource",
    ) -> None:
        if consumer is None and topic is None:
            raise TypeError("provide either consumer= or topic=")
        self._parameter_name = parameter_name
        self._consumer = consumer
        self._topic = topic
        self._bootstrap = bootstrap_servers
        self._group_id = group_id
        self._decoder = decoder or KafkaStreamingSource.__default_decoder
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def parameter_name(self) -> str:
        return self._parameter_name

    async def _ensure_consumer(self) -> Any:
        if self._consumer is None:
            try:
                from aiokafka import AIOKafkaConsumer
            except ImportError as exc:
                raise ImportError(
                    "KafkaStreamingSource requires aiokafka; install via `pip install pirn[kafka]`"
                ) from exc
            assert self._bootstrap is not None, "bootstrap_servers required when no consumer"
            self._consumer = AIOKafkaConsumer(
                self._topic,
                bootstrap_servers=self._bootstrap,
                group_id=self._group_id,
            )
            await self._consumer.start()
        return self._consumer

    async def stream(self) -> AsyncIterator[Any]:
        consumer = await self._ensure_consumer()
        async for msg in consumer:
            yield self._decoder(msg)

    async def close(self) -> None:
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                pass


    @staticmethod
    def __default_decoder(msg: Any) -> Any:
        raw = msg.value
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
