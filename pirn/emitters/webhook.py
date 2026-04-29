"""Webhook emitter — POST run events to configured HTTP endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.emitters.base import Emitter

if TYPE_CHECKING:
    from pirn.core.context import RunResult
    from pirn.core.lineage import KnotLineage
    from pirn.managers.status import StatusEvent


class WebhookEmitter(Emitter):
    """POSTs each event as JSON to one or more URLs.

    Per-event-type URLs are independent; pass ``None`` for any event
    type you don't care about.

    Construction:

    * ``WebhookEmitter(client=<httpx.AsyncClient>, ...)`` — inject a
      client (tests, custom timeouts, auth).
    * ``WebhookEmitter(url_status="...", ...)`` — build a client
      lazily.
    """

    def __init__(
        self,
        *,
        client: Any = None,
        url_status: str | None = None,
        url_lineage: str | None = None,
        url_result: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._client = client
        self._url_status = url_status
        self._url_lineage = url_lineage
        self._url_result = url_result
        self._timeout = timeout_seconds

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:
                raise ImportError(
                    "WebhookEmitter requires httpx; install via "
                    "`pip install pirn[http]`"
                ) from exc
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _post(self, url: str, payload: str) -> None:
        client = await self._ensure_client()
        await client.post(
            url,
            content=payload,
            headers={"Content-Type": "application/json"},
        )

    async def on_status(self, event: StatusEvent) -> None:
        if self._url_status is None:
            return
        await self._post(self._url_status, event.model_dump_json())

    async def on_lineage(self, record: KnotLineage) -> None:
        if self._url_lineage is None:
            return
        await self._post(self._url_lineage, record.model_dump_json())

    async def on_run_result(self, result: RunResult) -> None:
        if self._url_result is None:
            return
        await self._post(self._url_result, result.model_dump_json())

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
