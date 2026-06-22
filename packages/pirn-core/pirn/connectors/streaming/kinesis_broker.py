"""AWS Kinesis :class:`MessageBroker` backed by :mod:`aioboto3`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.connectors.message_broker import MessageBroker
from pirn.connectors.streaming.kinesis_config import KinesisConfig


class KinesisBroker(MessageBroker):
    """Kinesis broker over the asynchronous ``aioboto3`` client.

    Tests inject ``client=`` directly; production code constructs a real
    aioboto3 Kinesis client lazily on first use.
    """

    def __init__(
        self,
        config: KinesisConfig,
        *,
        client: Any | None = None,
    ) -> None:
        if not isinstance(config, KinesisConfig):
            raise TypeError(
                f"KinesisBroker.config must be KinesisConfig, got {type(config).__name__}"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> KinesisConfig:
        return self._config

    async def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            close_result = self._client.close()
            if hasattr(close_result, "__await__"):
                await close_result
        self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("kinesis.close")

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
                f"KinesisBroker.publish: value must be bytes, got {type(value).__name__}"
            )
        if key is not None and not isinstance(key, (bytes, bytearray)):
            raise TypeError(
                f"KinesisBroker.publish: key must be bytes or None, got {type(key).__name__}"
            )
        if headers is not None:
            for header_name, header_value in headers.items():
                if not isinstance(header_value, (bytes, bytearray)):
                    raise TypeError(
                        f"KinesisBroker.publish: header {header_name!r} must be bytes, "
                        f"got {type(header_value).__name__}"
                    )
        client = await self._ensure_client()
        partition_key = key.decode("utf-8") if key is not None else "default"
        await client.put_record(
            StreamName=topic,
            Data=bytes(value),
            PartitionKey=partition_key,
        )
        self._logger.debug("kinesis.publish", extra={"stream": topic, "size": len(value)})

    async def consume(
        self,
        topic: str,
        *,
        group: str | None = None,
    ) -> AsyncIterator[Any]:
        """Yield records from each shard of ``topic``.

        ``group`` is ignored — Kinesis has no consumer-group concept on the
        ``GetRecords`` path; use enhanced fan-out consumers via the AWS API
        directly if you need them.
        """
        client = await self._ensure_client()

        async def _iter() -> AsyncIterator[Any]:
            shards_response = await client.describe_stream(StreamName=topic)
            shards = shards_response["StreamDescription"]["Shards"]
            for shard in shards:
                shard_id = shard["ShardId"]
                iterator_response = await client.get_shard_iterator(
                    StreamName=topic,
                    ShardId=shard_id,
                    ShardIteratorType="TRIM_HORIZON",
                )
                shard_iterator = iterator_response["ShardIterator"]
                while shard_iterator is not None:
                    records_response = await client.get_records(ShardIterator=shard_iterator)
                    if "Records" not in records_response:
                        raise ValueError(
                            "KinesisBroker: get_records response missing required field 'Records'"
                        )
                    records = records_response["Records"]
                    if not records:
                        await asyncio.sleep(0)
                        break
                    for record in records:
                        yield record
                    # NextShardIterator is absent at end-of-shard
                    shard_iterator = records_response.get("NextShardIterator")

        return _iter()

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("KinesisBroker is closed")
        if self._client is None:
            self._client = await self._build_client()
        return self._client

    async def _build_client(self) -> Any:
        try:
            import aioboto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "KinesisBroker requires aioboto3; install via `pip install pirn[kinesis]`"
            ) from exc
        session = aioboto3.Session(
            aws_access_key_id=self._config.access_key_id,
            aws_secret_access_key=self._config.secret_access_key,
            aws_session_token=self._config.session_token,
            region_name=self._config.region,
        )
        kwargs: dict[str, Any] = {}
        if self._config.endpoint_url is not None:
            kwargs["endpoint_url"] = self._config.endpoint_url
        client_cm = session.client("kinesis", **kwargs)
        client = await client_cm.__aenter__()
        self._logger.debug("kinesis.connect")
        return client
