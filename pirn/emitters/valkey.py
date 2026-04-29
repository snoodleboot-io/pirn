"""ValKey pub/sub emitter — publish run events on ValKey channels."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.emitters.base import Emitter

if TYPE_CHECKING:
    from pirn.core.context import RunResult
    from pirn.core.lineage import KnotLineage
    from pirn.managers.status import StatusEvent


class ValKeyEmitter(Emitter):
    """Publishes events as JSON messages on ValKey pub/sub channels.

    Channels default to ``pirn:status``, ``pirn:lineage``,
    ``pirn:result``; override per-event-type as needed.
    """

    def __init__(
        self,
        *,
        client: Any = None,
        config: Any = None,
        channel_status: str = "pirn:status",
        channel_lineage: str = "pirn:lineage",
        channel_result: str = "pirn:result",
    ) -> None:
        if client is None and config is None:
            raise TypeError("provide either client= or config=")
        self._client = client
        self._config = config
        self._channel_status = channel_status
        self._channel_lineage = channel_lineage
        self._channel_result = channel_result

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from glide import GlideClient
            except ImportError as exc:
                raise ImportError(
                    "ValKeyEmitter requires valkey-glide; install via `pip install pirn[valkey]`"
                ) from exc
            self._client = await GlideClient.create(self._config)
        return self._client

    async def on_status(self, event: StatusEvent) -> None:
        client = await self._ensure_client()
        await client.publish(self._channel_status, event.model_dump_json())

    async def on_lineage(self, record: KnotLineage) -> None:
        client = await self._ensure_client()
        await client.publish(self._channel_lineage, record.model_dump_json())

    async def on_run_result(self, result: RunResult) -> None:
        client = await self._ensure_client()
        await client.publish(self._channel_result, result.model_dump_json())

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
