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
import logging
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING

from pirn.core.run_request import RunRequest
from pirn.core.shape_guard import ShapeGuard
from pirn.triggers.trigger import Trigger

if TYPE_CHECKING:
    from aiokafka import AIOKafkaConsumer, ConsumerRecord

_logger = logging.getLogger(__name__)


class KafkaTrigger(Trigger):
    """Trigger backed by an ``aiokafka`` consumer.

    Each Kafka message on the subscribed topic is converted into a
    ``RunRequest`` by the ``request_builder`` callable.  The default
    builder treats the message value as a JSON-encoded parameter dict.
    """

    def __init__(
        self,
        *,
        consumer: AIOKafkaConsumer | None = None,
        topic: str | None = None,
        bootstrap_servers: str | None = None,
        group_id: str = "pirn",
        request_builder: Callable[[ConsumerRecord], RunRequest] | None = None,
    ) -> None:
        """Initialise the trigger.

        Either ``consumer`` or ``topic`` must be supplied.

        Args:
            consumer: A pre-started ``aiokafka.AIOKafkaConsumer``
                instance.  When provided, ``topic``, ``bootstrap_servers``,
                and ``group_id`` are ignored.
            topic: Kafka topic to subscribe to.  Used to build a consumer
                lazily via ``bootstrap_servers`` on first ``stream()`` call.
            bootstrap_servers: Kafka bootstrap server string (e.g.
                ``"localhost:9092"``).  Required when ``consumer`` is
                ``None``.
            group_id: Kafka consumer group id.  Defaults to ``"pirn"``.
            request_builder: Callable ``(msg: ConsumerRecord) ->
                RunRequest``.  Defaults to JSON-decoding the message
                value as a parameter dict.

        Raises:
            TypeError: If neither ``consumer`` nor ``topic`` is given.
        """
        if consumer is None and topic is None:
            raise TypeError("provide either consumer= or topic=")
        self._consumer: AIOKafkaConsumer | None = consumer
        self._topic = topic
        self._bootstrap = bootstrap_servers
        self._group_id = group_id
        self._builder: Callable[[ConsumerRecord], RunRequest] = (
            request_builder or KafkaTrigger.__default_request_builder
        )

    @property
    def name(self) -> str:
        return "KafkaTrigger"

    async def _ensure_consumer(self) -> AIOKafkaConsumer:
        """Return the consumer, creating and starting one lazily if needed.

        Returns:
            A started ``aiokafka.AIOKafkaConsumer`` instance.

        Raises:
            ImportError: If ``aiokafka`` is not installed.
            AssertionError: If ``bootstrap_servers`` or ``topic`` was not
                provided when constructing without a consumer.
        """
        if self._consumer is None:
            try:
                from aiokafka import AIOKafkaConsumer
            except ImportError as exc:
                raise ImportError(
                    "KafkaTrigger requires aiokafka; install via `pip install pirn[kafka]`"
                ) from exc
            assert self._bootstrap is not None, "bootstrap_servers required when no consumer"
            assert self._topic is not None, "topic required when no consumer"
            consumer = AIOKafkaConsumer(
                self._topic,
                bootstrap_servers=self._bootstrap,
                group_id=self._group_id,
            )
            await consumer.start()
            self._consumer = consumer
        return self._consumer

    async def stream(self) -> AsyncIterator[RunRequest]:
        """Yield one ``RunRequest`` per consumed Kafka message.

        Starts the consumer on first call if it was not pre-supplied.
        Stops when the consumer is closed or the task is cancelled.

        Yields:
            One ``RunRequest`` per Kafka message received.
        """
        consumer = await self._ensure_consumer()
        async for msg in consumer:
            yield self._builder(msg)

    async def close(self) -> None:
        """Stop the Kafka consumer and release its resources."""
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                _logger.warning("KafkaTrigger: consumer.stop() raised during close", exc_info=True)

    @staticmethod
    def __default_request_builder(msg: ConsumerRecord) -> RunRequest:
        raw = msg.value
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        # A value a deserializer already decoded is taken as it is.
        params: object = json.loads(raw) if isinstance(raw, str) else raw
        if not ShapeGuard.is_str_keyed_dict(params):
            raise TypeError(
                f"KafkaTrigger: expected JSON object for message value, got {type(params).__name__}"
            )
        return RunRequest(parameters=params)
