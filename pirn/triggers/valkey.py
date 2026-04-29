"""ValKey pub/sub trigger.

Subscribes to a ValKey channel; each published message becomes a
``RunRequest``.  Uses ``valkey-glide`` for the underlying connection.

Pair with ``ValKeyEmitter`` for symmetric producer/consumer flows
inside a pirn-only architecture.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.context import RunRequest


class ValKeyTrigger:
    """Trigger backed by a ValKey pub/sub subscription."""

    def __init__(
        self,
        *,
        client: Any = None,
        channel: str | None = None,
        config: Any = None,
        request_builder: Any = None,
    ) -> None:
        if client is None and channel is None:
            raise TypeError("provide either client= or channel=")
        self._client = client
        self._channel = channel
        self._config = config
        self._builder = request_builder or _default_request_builder
        self._closed = False

    @property
    def name(self) -> str:
        return "ValKeyTrigger"

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from glide import GlideClient
            except ImportError as exc:
                raise ImportError(
                    "ValKeyTrigger requires valkey-glide; install via `pip install pirn[valkey]`"
                ) from exc
            # The user's config must include pubsub_subscriptions for
            # this trigger to receive messages; we don't attempt to
            # rewrite it here.
            self._client = await GlideClient.create(self._config)
        return self._client

    async def stream(self) -> AsyncIterator[RunRequest]:
        client = await self._ensure_client()
        # valkey-glide exposes pubsub messages either via callback (set
        # in the config) or via get_pubsub_message().  We iterate the
        # latter for a clean async-iterator surface.
        while not self._closed:
            msg = await client.get_pubsub_message()
            if msg is None:
                continue
            yield self._builder(msg)

    async def close(self) -> None:
        self._closed = True


def _default_request_builder(msg: Any) -> RunRequest:
    """Default: message body is JSON; decoded into RunRequest parameters."""
    body = getattr(msg, "message", msg)
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    if isinstance(body, str):
        params = json.loads(body)
    else:
        params = body
    if not isinstance(params, dict):
        raise TypeError(
            f"ValKeyTrigger: expected JSON object for message, got {type(params).__name__}"
        )
    return RunRequest(parameters=params)
