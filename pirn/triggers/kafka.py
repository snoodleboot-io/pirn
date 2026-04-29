"""Kafka trigger.

Consumes from a Kafka topic via ``aiokafka``; each message becomes a
``RunRequest``.  The default builder treats the message value as a
JSON-encoded parameter dict, but a custom ``request_builder`` can be
provided for richer mappings (e.g., reading message headers, keys, or
specific Avro/Protobuf payloads).

Construction:

* ``KafkaTrigger(consumer=<aiokafka.AIOKafkaConsumer>, ...)`` — inject
  an existing consumer (tests, advanced setups).
* ``KafkaTrigger(topic="my-topic", bootstrap_servers="...", ...)`` —
  build a consumer lazily on first stream.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class KafkaTrigger(Trigger):
    """Trigger backed by an aiokafka consumer."""

    def __init__(
        self,
        *,
        consumer: Any = None,
        topic: str | None = None,
        bootstrap_servers: str | None = None,
        group_id: str = "pirn",
        request_builder: Any = None,
    ) -> None:
        if consumer is None and topic is None:
            raise TypeError("provide either consumer= or topic=")
        self._consumer = consumer
        self._topic = topic
        self._bootstrap = bootstrap_servers
        self._group_id = group_id
        self._builder = request_builder or KafkaTrigger.__default_request_builder

    @property
    def name(self) -> str:
        return "KafkaTrigger"

    async def _ensure_consumer(self) -> Any:
        if self._consumer is None:
            try:
                from aiokafka import AIOKafkaConsumer
            except ImportError as exc:
                raise ImportError(
                    "KafkaTrigger requires aiokafka; install via `pip install pirn[kafka]`"
                ) from exc
            assert self._bootstrap is not None, "bootstrap_servers required when no consumer"
            self._consumer = AIOKafkaConsumer(
                self._topic,
                bootstrap_servers=self._bootstrap,
                group_id=self._group_id,
            )
            await self._consumer.start()
        return self._consumer

    async def stream(self) -> AsyncIterator[RunRequest]:
        consumer = await self._ensure_consumer()
        async for msg in consumer:
            yield self._builder(msg)

    async def close(self) -> None:
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                pass


    @staticmethod
    def __default_request_builder(msg: Any) -> RunRequest:
        raw = msg.value
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            params = json.loads(raw)
        else:
            params = raw
        if not isinstance(params, dict):
            raise TypeError(
                f"KafkaTrigger: expected JSON object for message value, got {type(params).__name__}"
            )
        return RunRequest(parameters=params)
