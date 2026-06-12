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

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger


class ValKeyTrigger(Trigger):
    """Trigger backed by a ValKey pub/sub subscription.

    Each message published to the configured channel is converted into
    a ``RunRequest`` by the ``request_builder`` callable.  The default
    builder JSON-decodes the message body as a parameter dict.

    Pair with ``ValKeyEmitter`` for symmetric producer/consumer flows
    within a pirn-only architecture.
    """

    def __init__(
        self,
        *,
        client: Any = None,
        channel: str | None = None,
        config: Any = None,
        request_builder: Any = None,
    ) -> None:
        """Initialise the trigger.

        Either ``client`` or ``channel`` must be supplied.

        Args:
            client: A pre-created ``valkey-glide`` ``GlideClient``
                instance.  When provided, ``config`` is ignored.
            channel: ValKey pub/sub channel to subscribe to.  Used
                to identify the trigger; the channel subscription must
                be configured on the ``GlideClientConfiguration`` passed
                via ``config``.
            config: A ``GlideClientConfiguration`` (or compatible object)
                used to create a ``GlideClient`` lazily on first use.
                Requires ``pirn[valkey]``.
            request_builder: Callable ``(msg) -> RunRequest``.  Receives
                the raw pub/sub message object from ``valkey-glide``.
                Defaults to JSON-decoding ``msg.message`` as a parameter
                dict.

        Raises:
            TypeError: If neither ``client`` nor ``channel`` is given.
        """
        if client is None and channel is None:
            raise TypeError("provide either client= or channel=")
        self._client = client
        self._channel = channel
        self._config = config
        self._builder = request_builder or ValKeyTrigger.__default_request_builder
        self._closed = False

    @property
    def name(self) -> str:
        return "ValKeyTrigger"

    async def _ensure_client(self) -> Any:
        """Return the ValKey client, creating one lazily if needed.

        Returns:
            A connected ``GlideClient`` instance.

        Raises:
            ImportError: If ``valkey-glide`` is not installed.
        """
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
        """Yield one ``RunRequest`` per ValKey pub/sub message received.

        Polls ``client.get_pubsub_message()`` in a loop.  Skips ``None``
        returns (no message available yet) and exits when ``close()`` is
        called.

        Yields:
            One ``RunRequest`` per message received on the channel.
        """
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
        """Signal the trigger to stop polling after the current iteration."""
        self._closed = True

    @staticmethod
    def __default_request_builder(msg: Any) -> RunRequest:
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
