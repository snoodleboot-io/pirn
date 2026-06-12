"""Kafka :class:`MessageBroker` backed by :mod:`aiokafka`."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from pirn.connectors.message_broker import MessageBroker
from pirn.connectors.streaming.kafka_config import KafkaConfig


class KafkaBroker(MessageBroker):
    """Kafka producer + consumer broker.

    Tests inject ``producer=`` and ``consumer_factory=``; production code
    constructs real aiokafka clients lazily on first use.
    """

    def __init__(
        self,
        config: KafkaConfig,
        *,
        producer: Any | None = None,
        consumer_factory: Callable[[str, str | None], Any] | None = None,
    ) -> None:
        self._config = config
        self._producer = producer
        self._consumer_factory = consumer_factory
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> KafkaConfig:
        return self._config

    async def close(self) -> None:
        if self._producer is not None and hasattr(self._producer, "stop"):
            await self._producer.stop()
        self._producer = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("kafka.close")

    async def publish(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: dict[str, bytes] | None = None,
    ) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(f"KafkaBroker.publish: value must be bytes, got {type(value).__name__}")
        if key is not None and not isinstance(key, (bytes, bytearray)):
            raise TypeError(
                f"KafkaBroker.publish: key must be bytes or None, got {type(key).__name__}"
            )
        producer = await self._ensure_producer()
        header_pairs = list(headers.items()) if headers else None
        await producer.send_and_wait(
            topic,
            value=bytes(value),
            key=bytes(key) if key is not None else None,
            headers=header_pairs,
        )
        self._logger.debug("kafka.publish", extra={"topic": topic, "size": len(value)})

    async def consume(
        self,
        topic: str,
        *,
        group: str | None = None,
    ) -> AsyncIterator[Any]:
        effective_group = group or self._config.group_id
        if self._consumer_factory is not None:
            consumer = self._consumer_factory(topic, effective_group)
        else:
            consumer = await self._build_consumer(topic, effective_group)

        async def _iter() -> AsyncIterator[Any]:
            await consumer.start()
            try:
                async for record in consumer:
                    yield record
            finally:
                await consumer.stop()

        return _iter()

    async def _ensure_producer(self) -> Any:
        if self._closed:
            raise RuntimeError("KafkaBroker is closed")
        if self._producer is None:
            self._producer = await self._build_producer()
        return self._producer

    async def _build_producer(self) -> Any:
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError as exc:
            raise ImportError(
                "KafkaBroker requires aiokafka; install via `pip install pirn[kafka]`"
            ) from exc
        kwargs: dict[str, Any] = dict(self._config.extra_producer_config)
        kwargs.update(
            bootstrap_servers=self._config.bootstrap_servers,
            client_id=self._config.client_id,
            security_protocol=self._config.security_protocol,
        )
        if self._config.sasl_mechanism:
            kwargs.update(
                sasl_mechanism=self._config.sasl_mechanism,
                sasl_plain_username=self._config.sasl_username,
                sasl_plain_password=self._config.sasl_password,
            )
        if self._config.ssl_cafile:
            kwargs.update(ssl_cafile=self._config.ssl_cafile)
        producer = AIOKafkaProducer(**kwargs)
        await producer.start()
        self._logger.debug("kafka.producer.start")
        return producer

    async def _build_consumer(self, topic: str, effective_group: str | None) -> Any:
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError as exc:
            raise ImportError(
                "KafkaBroker requires aiokafka; install via `pip install pirn[kafka]`"
            ) from exc
        kwargs: dict[str, Any] = dict(self._config.extra_consumer_config)
        kwargs.update(
            bootstrap_servers=self._config.bootstrap_servers,
            client_id=self._config.client_id,
            group_id=effective_group,
            security_protocol=self._config.security_protocol,
        )
        if self._config.sasl_mechanism:
            kwargs.update(
                sasl_mechanism=self._config.sasl_mechanism,
                sasl_plain_username=self._config.sasl_username,
                sasl_plain_password=self._config.sasl_password,
            )
        return AIOKafkaConsumer(topic, **kwargs)
