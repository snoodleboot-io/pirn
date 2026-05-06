"""Google Pub/Sub :class:`MessageBroker` backed by ``google-cloud-pubsub``."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.pubsub_config import PubSubConfig


class PubSubBroker(MessageBroker):
    """Pub/Sub broker that wraps the synchronous Google client in threads.

    The official ``google-cloud-pubsub`` client is callback-based and
    blocking. To preserve pirn's async contract we run publisher / subscriber
    calls inside :func:`asyncio.to_thread`. Tests inject ``publisher=`` and
    ``subscriber=`` stubs directly.
    """

    def __init__(
        self,
        config: PubSubConfig,
        *,
        publisher: Any | None = None,
        subscriber: Any | None = None,
    ) -> None:
        if not isinstance(config, PubSubConfig):
            raise TypeError(
                f"PubSubBroker.config must be PubSubConfig, got {type(config).__name__}"
            )
        self._config = config
        self._publisher = publisher
        self._subscriber = subscriber
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> PubSubConfig:
        return self._config

    async def close(self) -> None:
        for client in (self._publisher, self._subscriber):
            if client is None:
                continue
            close = getattr(client, "close", None)
            if close is None:
                continue
            result = close()
            if hasattr(result, "__await__"):
                await result
        self._publisher = None
        self._subscriber = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("pubsub.close")

    async def publish(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: dict[str, bytes] | None = None,
    ) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(
                f"PubSubBroker.publish: value must be bytes, got {type(value).__name__}"
            )
        if key is not None and not isinstance(key, (bytes, bytearray)):
            raise TypeError(
                f"PubSubBroker.publish: key must be bytes or None, got {type(key).__name__}"
            )
        if headers is not None:
            for header_name, header_value in headers.items():
                if not isinstance(header_value, (bytes, bytearray)):
                    raise TypeError(
                        f"PubSubBroker.publish: header {header_name!r} must be bytes, "
                        f"got {type(header_value).__name__}"
                    )
        publisher = await self._ensure_publisher()
        topic_path = self._topic_path(publisher, topic)
        attributes: dict[str, str] = {}
        if key is not None:
            attributes["pirn-key"] = key.decode("utf-8")
        if headers:
            for header_name, header_value in headers.items():
                attributes[header_name] = header_value.decode("utf-8")

        def _publish_sync() -> str:
            future = publisher.publish(topic_path, bytes(value), **attributes)
            return future.result()

        await asyncio.to_thread(_publish_sync)
        self._logger.debug(
            "pubsub.publish", extra={"topic": topic, "size": len(value)}
        )

    async def consume(
        self,
        topic: str,
        *,
        group: str | None = None,
    ) -> AsyncIterator[Any]:
        """Pull messages from a Pub/Sub *subscription*.

        Pub/Sub distinguishes topics (publish endpoints) from subscriptions
        (consume endpoints). For :meth:`publish`, ``topic`` is a topic name.
        For :meth:`consume`, ``topic`` is a subscription name. ``group`` is
        ignored — Pub/Sub already scopes message delivery per subscription.
        """
        subscriber = await self._ensure_subscriber()
        subscription_path = self._subscription_path(subscriber, topic)

        async def _iter() -> AsyncIterator[Any]:
            while True:
                response = await asyncio.to_thread(
                    subscriber.pull,
                    request={"subscription": subscription_path, "max_messages": 100},
                )
                received = getattr(response, "received_messages", []) or []
                if not received:
                    return
                ack_ids: list[str] = []
                for received_message in received:
                    yield received_message
                    ack_id = getattr(received_message, "ack_id", None)
                    if ack_id is not None:
                        ack_ids.append(ack_id)
                if ack_ids:
                    await asyncio.to_thread(
                        subscriber.acknowledge,
                        request={
                            "subscription": subscription_path,
                            "ack_ids": ack_ids,
                        },
                    )

        return _iter()

    async def _ensure_publisher(self) -> Any:
        if self._closed:
            raise RuntimeError("PubSubBroker is closed")
        if self._publisher is None:
            self._publisher = await self._build_publisher()
        return self._publisher

    async def _ensure_subscriber(self) -> Any:
        if self._closed:
            raise RuntimeError("PubSubBroker is closed")
        if self._subscriber is None:
            self._subscriber = await self._build_subscriber()
        return self._subscriber

    async def _build_publisher(self) -> Any:
        try:
            from google.cloud import pubsub_v1  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "PubSubBroker requires google-cloud-pubsub; install via "
                "`pip install pirn[pubsub]`"
            ) from exc
        kwargs: dict[str, Any] = {}
        if self._config.service_account_json is not None:
            from google.oauth2 import service_account  # type: ignore[import-untyped]

            kwargs["credentials"] = (
                service_account.Credentials.from_service_account_file(
                    self._config.service_account_json
                )
            )
        return pubsub_v1.PublisherClient(**kwargs)

    async def _build_subscriber(self) -> Any:
        try:
            from google.cloud import pubsub_v1  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "PubSubBroker requires google-cloud-pubsub; install via "
                "`pip install pirn[pubsub]`"
            ) from exc
        kwargs: dict[str, Any] = {}
        if self._config.service_account_json is not None:
            from google.oauth2 import service_account  # type: ignore[import-untyped]

            kwargs["credentials"] = (
                service_account.Credentials.from_service_account_file(
                    self._config.service_account_json
                )
            )
        return pubsub_v1.SubscriberClient(**kwargs)

    def _topic_path(self, publisher: Any, topic: str) -> str:
        if "/" in topic:
            return topic
        if self._config.project is None:
            raise ValueError(
                "PubSubBroker.publish: topic must be a fully-qualified path "
                "or PubSubConfig.project must be set"
            )
        topic_path = getattr(publisher, "topic_path", None)
        if topic_path is None:
            return f"projects/{self._config.project}/topics/{topic}"
        return topic_path(self._config.project, topic)

    def _subscription_path(self, subscriber: Any, subscription: str) -> str:
        if "/" in subscription:
            return subscription
        if self._config.project is None:
            raise ValueError(
                "PubSubBroker.consume: subscription must be a fully-qualified "
                "path or PubSubConfig.project must be set"
            )
        subscription_path = getattr(subscriber, "subscription_path", None)
        if subscription_path is None:
            return (
                f"projects/{self._config.project}/subscriptions/{subscription}"
            )
        return subscription_path(self._config.project, subscription)
