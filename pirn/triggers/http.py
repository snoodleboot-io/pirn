"""HTTP webhook trigger.

Exposes a Starlette ASGI application; each POST to the trigger's
endpoint enqueues a ``RunRequest`` for the runtime to consume.

The trigger itself just yields requests from an internal queue.  The
Starlette app is exposed as ``trigger.app`` for the user to mount on
any ASGI server (uvicorn, hypercorn) or compose into an existing
FastAPI/Starlette application.

Construction:

* ``WebhookTrigger(path="/run")`` — single endpoint, no auth.
* ``WebhookTrigger(path="/run", auth_token=os.environ["PIRN_WEBHOOK_TOKEN"])``
  — Bearer-token auth; requests without a matching ``Authorization: Bearer
  <token>`` header receive HTTP 401.  The comparison uses
  ``hmac.compare_digest`` to prevent timing-based token enumeration.
* ``WebhookTrigger(path="/run", rate_limit_rpm=60)`` — sliding-window
  per-IP rate limit (requests per minute).  Requests exceeding the limit
  receive HTTP 429.
* ``WebhookTrigger(path="/run", request_builder=...)`` — custom
  parameter extraction (e.g., from headers, query params, or specific
  JSON shapes).

Parameters
----------
path:
    URL path for the POST endpoint.
request_builder:
    Callable ``(payload: dict, request) -> RunRequest``.  Defaults to
    treating the JSON body as the ``RunRequest`` parameters dict.
auth_token:
    Optional Bearer token.  When set every inbound request must supply
    ``Authorization: Bearer <token>``; mismatches return HTTP 401.
rate_limit_rpm:
    Optional per-IP request-per-minute cap enforced via a 60-second
    sliding window.  Excess requests return HTTP 429.

Note: only the trigger's app is provided.  Wiring the app to a server
is the user's responsibility — that's the right separation, since
webhook hosting decisions (TLS, CORS) belong to the deployment.
"""

from __future__ import annotations

import asyncio
import collections
import hmac as _hmac
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class WebhookTrigger(Trigger):
    """HTTP-driven trigger; exposes a Starlette app for serving."""

    def __init__(
        self,
        *,
        path: str = "/run",
        request_builder: Any = None,
        auth_token: str | None = None,
        rate_limit_rpm: int | None = None,
    ) -> None:
        self._path = path
        self._builder = request_builder or _default_request_builder
        self._auth_token = auth_token
        self._rate_limit_rpm = rate_limit_rpm
        self._rate_windows: dict = collections.defaultdict(collections.deque)
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

    async def _handle_request(self, request: Any) -> Any:
        try:
            from starlette.responses import JSONResponse
        except ImportError as exc:
            raise ImportError(
                "WebhookTrigger requires starlette; install via `pip install pirn[http]`"
            ) from exc

        if self._auth_token is not None:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            provided = auth_header[len("Bearer "):]
            if not _hmac.compare_digest(provided, self._auth_token):
                return JSONResponse({"error": "unauthorized"}, status_code=401)

        if self._rate_limit_rpm is not None:
            client_ip = request.client.host if request.client else "unknown"
            window = self._rate_windows[client_ip]
            now = time.monotonic()
            while window and now - window[0] > 60.0:
                window.popleft()
            if len(window) >= self._rate_limit_rpm:
                return JSONResponse({"error": "rate limit exceeded"}, status_code=429)
            window.append(now)

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

    def _build_app(self) -> Any:
        try:
            from starlette.applications import Starlette
            from starlette.routing import Route
        except ImportError as exc:
            raise ImportError(
                "WebhookTrigger requires starlette; install via `pip install pirn[http]`"
            ) from exc

        return Starlette(routes=[Route(self._path, self._handle_request, methods=["POST"])])

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
        raise TypeError(f"WebhookTrigger: expected JSON object body, got {type(payload).__name__}")
    return RunRequest(parameters=payload)
