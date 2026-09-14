"""ValKey pub/sub trigger.

Subscribes to a ValKey channel; each published message becomes a
``RunRequest``.  Uses ``valkey-glide`` for the underlying connection.

Pair with ``ValKeyEmitter`` for symmetric producer/consumer flows
inside a pirn-only architecture.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING

from pirn.core.optional_dependency import OptionalDependency
from pirn.core.run_request import RunRequest
from pirn.core.shape_guard import ShapeGuard
from pirn.triggers.trigger import Trigger

if TYPE_CHECKING:
    from glide import GlideClient, GlideClientConfiguration, PubSubMsg


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
        client: GlideClient | None = None,
        channel: str | None = None,
        config: GlideClientConfiguration | None = None,
        request_builder: Callable[[PubSubMsg], RunRequest] | None = None,
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
            config: A ``GlideClientConfiguration``
                used to create a ``GlideClient`` lazily on first use.
                Requires ``pirn-core[valkey]``.
            request_builder: Callable ``(msg) -> RunRequest``.  Receives
                the raw pub/sub message object from ``valkey-glide``.
                Defaults to JSON-decoding ``msg.message`` as a parameter
                dict.

        Raises:
            TypeError: If neither ``client`` nor ``channel`` is given.
        """
        if client is None and channel is None:
            raise TypeError("provide either client= or channel=")
        self._client: GlideClient | None = client
        self._channel = channel
        self._config: GlideClientConfiguration | None = config
        self._builder: Callable[[PubSubMsg], RunRequest] = (
            request_builder or ValKeyTrigger.__default_request_builder
        )
        self._closed = False

    @property
    def name(self) -> str:
        return "ValKeyTrigger"

    async def _ensure_client(self) -> GlideClient:
        """Return the ValKey client, creating one lazily if needed.

        Returns:
            A connected ``GlideClient`` instance.

        Raises:
            ImportError: If ``valkey-glide`` is not installed.
            TypeError: If no client was injected and no ``config`` was given.
        """
        if self._client is None:
            glide = OptionalDependency.require("glide", extra="valkey")
            # The user's config must include pubsub_subscriptions for
            # this trigger to receive messages; we don't attempt to
            # rewrite it here.
            if self._config is None:
                raise TypeError("ValKeyTrigger: config= is required when no client= is given")
            client: GlideClient = await glide.GlideClient.create(self._config)
            self._client = client
        return self._client

    async def stream(self) -> AsyncIterator[RunRequest]:
        """Yield one ``RunRequest`` per ValKey pub/sub message received.

        Awaits ``client.get_pubsub_message()`` in a loop and exits when
        ``close()`` is called.

        Yields:
            One ``RunRequest`` per message received on the channel.
        """
        client = await self._ensure_client()
        # valkey-glide exposes pubsub messages either via callback (set
        # in the config) or via get_pubsub_message().  We iterate the
        # latter for a clean async-iterator surface.
        while not self._closed:
            msg = await client.get_pubsub_message()
            yield self._builder(msg)

    async def close(self) -> None:
        """Signal the trigger to stop polling after the current iteration."""
        self._closed = True

    @staticmethod
    def __default_request_builder(msg: PubSubMsg) -> RunRequest:
        body = msg.message
        params: object = json.loads(body if isinstance(body, str) else bytes(body).decode("utf-8"))
        if not ShapeGuard.is_str_keyed_dict(params):
            raise TypeError(
                f"ValKeyTrigger: expected JSON object for message, got {type(params).__name__}"
            )
        return RunRequest(parameters=params)
