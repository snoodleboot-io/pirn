"""HTTP webhook trigger.

Exposes a Starlette ASGI application; each POST to the trigger's
endpoint enqueues a ``RunRequest`` for the runtime to consume.

The trigger itself just yields requests from an internal queue.  The
Starlette app is exposed as ``trigger.app`` for the user to mount on
any ASGI server (uvicorn, hypercorn) or compose into an existing
FastAPI/Starlette application.

Construction:

* ``WebhookTrigger(path="/run")`` — single endpoint.
* ``WebhookTrigger(path="/run", request_builder=...)`` — custom
  parameter extraction (e.g., from headers, query params, or specific
  JSON shapes).

Note: only the trigger's app is provided.  Wiring the app to a server
is the user's responsibility — that's the right separation, since
webhook hosting decisions (TLS, auth, rate limiting, CORS) belong to
the deployment, not to the trigger.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.context import RunRequest


class WebhookTrigger:
    """HTTP-driven trigger; exposes a Starlette app for serving."""

    def __init__(
        self,
        *,
        path: str = "/run",
        request_builder: Any = None,
    ) -> None:
        self._path = path
        self._builder = request_builder or _default_request_builder
        self._queue: asyncio.Queue[RunRequest] = asyncio.Queue()
        self._closed = False
        # Sentinel pushed on close() to wake the consumer.
        self._SENTINEL: Any = object()
        # Build the ASGI app lazily in case starlette isn't installed.
        self._app: Any = None

    @property
    def name(self) -> str:
        return "WebhookTrigger"

    @property
    def app(self) -> Any:
        """The Starlette ASGI app exposing this trigger's endpoint.

        Mount on any ASGI server::

            import uvicorn
            uvicorn.run(trigger.app, host="0.0.0.0", port=8080)
        """
        if self._app is None:
            self._app = self._build_app()
        return self._app

    def _build_app(self) -> Any:
        try:
            from starlette.applications import Starlette
            from starlette.responses import JSONResponse
            from starlette.routing import Route
        except ImportError as exc:
            raise ImportError(
                "WebhookTrigger requires starlette; install via "
                "`pip install pirn[http]`"
            ) from exc

        async def handler(request):
            try:
                body = await request.body()
                payload = json.loads(body) if body else {}
                run_request = self._builder(payload, request)
            except Exception as exc:
                return JSONResponse(
                    {"error": f"failed to build RunRequest: {exc}"},
                    status_code=400,
                )
            await self._queue.put(run_request)
            return JSONResponse({"run_id": run_request.run_id, "queued": True})

        return Starlette(routes=[Route(self._path, handler, methods=["POST"])])

    async def stream(self) -> AsyncIterator[RunRequest]:
        while not self._closed:
            item = await self._queue.get()
            if item is self._SENTINEL:
                return
            yield item

    async def submit(self, request: RunRequest) -> None:
        """Push a request onto the queue programmatically (tests / direct
        use without HTTP)."""
        await self._queue.put(request)

    async def close(self) -> None:
        self._closed = True
        await self._queue.put(self._SENTINEL)


def _default_request_builder(payload: dict, request: Any) -> RunRequest:
    """Default: payload is the parameters dict."""
    if not isinstance(payload, dict):
        raise TypeError(
            f"WebhookTrigger: expected JSON object body, "
            f"got {type(payload).__name__}"
        )
    return RunRequest(parameters=payload)
