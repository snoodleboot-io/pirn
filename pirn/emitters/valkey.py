"""ValKey pub/sub emitter — publish run events on ValKey channels."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.emitters.base import Emitter

if TYPE_CHECKING:
    from pirn.core.lineage import KnotLineage
    from pirn.core.run_result import RunResult
    from pirn.managers.status_event import StatusEvent


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
        """Initialise the emitter.

        Either ``client`` or ``config`` must be supplied.

        Args:
            client: A pre-created ``valkey-glide`` ``GlideClient``
                instance.  When provided, ``config`` is ignored.
            config: A ``GlideClientConfiguration`` (or compatible object)
                used to create a ``GlideClient`` lazily on first use.
                Requires ``pirn[valkey]``.
            channel_status: ValKey pub/sub channel for status events.
                Defaults to ``"pirn:status"``.
            channel_lineage: ValKey pub/sub channel for lineage records.
                Defaults to ``"pirn:lineage"``.
            channel_result: ValKey pub/sub channel for run results.
                Defaults to ``"pirn:result"``.

        Raises:
            TypeError: If neither ``client`` nor ``config`` is given.
        """
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
        """Publishes a JSON-serialised status event to the configured ValKey channel.

        Args:
            event: The status event to publish.
        """
        client = await self._ensure_client()
        await client.publish(self._channel_status, event.model_dump_json())

    async def on_lineage(self, record: KnotLineage) -> None:
        """Publishes a JSON-serialised lineage record to the configured ValKey channel.

        Args:
            record: The knot lineage record to publish.
        """
        client = await self._ensure_client()
        await client.publish(self._channel_lineage, record.model_dump_json())

    async def on_run_result(self, result: RunResult) -> None:
        """Publishes a JSON-serialised run result to the configured ValKey channel.

        Args:
            result: The completed run result to publish.
        """
        client = await self._ensure_client()
        await client.publish(self._channel_result, result.model_dump_json())

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
