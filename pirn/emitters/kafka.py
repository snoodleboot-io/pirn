"""Kafka emitter — publish run events to a Kafka topic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.emitters.base import Emitter

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.core.lineage import KnotLineage
    from pirn.managers.status_event import StatusEvent


class KafkaEmitter(Emitter):
    """Publishes events as JSON messages on a Kafka topic.

    Three event types share one topic by default; use ``topic_status``,
    ``topic_lineage``, and ``topic_result`` for separate topics.

    Construction:

    * ``KafkaEmitter(producer=<aiokafka.AIOKafkaProducer>, ...)`` —
      inject a producer (tests, advanced setups).
    * ``KafkaEmitter(topic="pirn-events", bootstrap_servers="...")``
      — build a producer lazily.
    """

    def __init__(
        self,
        *,
        producer: Any = None,
        topic: str | None = None,
        bootstrap_servers: str | None = None,
        topic_status: str | None = None,
        topic_lineage: str | None = None,
        topic_result: str | None = None,
    ) -> None:
        if producer is None and topic is None:
            raise TypeError("provide either producer= or topic=")
        self._producer = producer
        self._topic_default = topic
        self._bootstrap = bootstrap_servers
        self._topic_status = topic_status or topic
        self._topic_lineage = topic_lineage or topic
        self._topic_result = topic_result or topic

    async def _ensure_producer(self) -> Any:
        if self._producer is None:
            try:
                from aiokafka import AIOKafkaProducer
            except ImportError as exc:
                raise ImportError(
                    "KafkaEmitter requires aiokafka; install via `pip install pirn[kafka]`"
                ) from exc
            assert self._bootstrap is not None, "bootstrap_servers required when no producer"
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap,
            )
            await self._producer.start()
        return self._producer

    async def _send(self, topic: str, payload: bytes, key: bytes | None) -> None:
        producer = await self._ensure_producer()
        await producer.send_and_wait(topic, payload, key=key)

    async def on_status(self, event: StatusEvent) -> None:
        if self._topic_status is None:
            return
        await self._send(
            self._topic_status,
            event.model_dump_json().encode("utf-8"),
            key=event.run_id.encode("utf-8"),
        )

    async def on_lineage(self, record: KnotLineage) -> None:
        if self._topic_lineage is None:
            return
        await self._send(
            self._topic_lineage,
            record.model_dump_json().encode("utf-8"),
            key=record.run_id.encode("utf-8"),
        )

    async def on_run_result(self, result: RunResult) -> None:
        if self._topic_result is None:
            return
        await self._send(
            self._topic_result,
            result.model_dump_json().encode("utf-8"),
            key=result.run_id.encode("utf-8"),
        )

    async def close(self) -> None:
        if self._producer is not None:
            try:
                await self._producer.stop()
            except Exception:
                pass
