from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pirn.backends.base.subscribable_store import SubscribableStore

_logger = logging.getLogger(__name__)
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot  # noqa: E402
from pirn.backends.base.tapestry_store import TapestryStore  # noqa: E402
from pirn.backends.valkey._lazy_client import _LazyClient  # noqa: E402

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class ValKeyStore(TapestryStore, SubscribableStore):
    """TapestryStore backed by ValKey.

    Live knot references are kept in-process; ValKey holds a sorted set
    of knot ids and a hash per knot. Cross-process queries read the
    snapshot without touching live Python objects.
    """

    _ids_key = "pirn:tapestry:ids"
    _knot_key_prefix = "pirn:tapestry:knot:"
    _registrations_channel = "pirn:tapestry:registrations"

    def __init__(self, *, client: Any = None, config: Any = None) -> None:
        """Initialise the store.

        Args:
            client: An existing ``GlideClient`` instance to reuse.  Suitable
                for tests or when sharing a client across components.
            config: A ``GlideClientConfiguration`` used to create a client
                lazily on first use.  Mutually exclusive with ``client``.

        Raises:
            TypeError: If neither ``client`` nor ``config`` is provided.
        """
        self._client = _LazyClient(client=client, config=config)
        self._live: dict[str, Knot] = {}
        self._pending_register_tasks: list[Any] = []
        self._subscribers: dict[int, Callable[[Any], None]] = {}
        self._next_token: int = 0
        self._listener_task: asyncio.Task[None] | None = None

    async def aregister(self, knot: Knot) -> None:
        """Async variant of :meth:`register`.

        Persists the knot metadata to ValKey and, if any subscribers are
        active, publishes the knot id to the registrations pub/sub channel.

        Args:
            knot: The knot to register.

        Raises:
            ValueError: If a different ``Knot`` instance with the same
                ``knot_id`` is already registered.
        """
        existing = self._live.get(knot.knot_id)
        if existing is not None and existing is not knot:
            raise ValueError(
                f"knot id {knot.knot_id!r} already registered with a different instance"
            )
        self._live[knot.knot_id] = knot

        client = await self._client.get()
        config_json = knot.config.model_dump_json()
        parents_json = json.dumps({name: parent.knot_id for name, parent in knot.parents.items()})
        knot_class = f"{type(knot).__module__}.{type(knot).__qualname__}"
        knot_key = f"{self._knot_key_prefix}{knot.knot_id}"

        await client.hset(
            knot_key,
            {
                "knot_class": knot_class,
                "config_json": config_json,
                "parents_json": parents_json,
            },
        )
        await client.sadd(self._ids_key, [knot.knot_id])
        if self._subscribers:
            await client.publish(self._registrations_channel, knot.knot_id)

    def register(self, knot: Knot) -> None:
        """Register a knot, dispatching to the async path appropriately.

        If no event loop is running the registration is executed synchronously
        via ``asyncio.run``.  If a loop is already running the in-process dict
        is updated immediately and the ValKey write is scheduled as a
        background task.

        Args:
            knot: The knot to register.

        Raises:
            ValueError: If a different ``Knot`` instance with the same
                ``knot_id`` is already registered.
        """
        existing = self._live.get(knot.knot_id)
        if existing is not None and existing is not knot:
            raise ValueError(
                f"knot id {knot.knot_id!r} already registered with a different instance"
            )
        self._live[knot.knot_id] = knot
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.aregister(knot))
            return
        self._pending_register_tasks.append(asyncio.ensure_future(self.aregister(knot)))

    def get(self, knot_id: str) -> Knot | None:
        """Return the in-process ``Knot`` for ``knot_id``, or ``None``.

        Args:
            knot_id: Identifier of the knot to retrieve.

        Returns:
            The registered ``Knot`` instance, or ``None`` if not found.
        """
        return self._live.get(knot_id)

    def all(self) -> list[Knot]:
        """Return all registered knots held in memory.

        Returns:
            List of ``Knot`` instances in insertion order.
        """
        return list(self._live.values())

    def snapshot(self) -> TapestrySnapshot:
        """Return a snapshot of currently registered knot ids.

        Returns:
            A frozen ``TapestrySnapshot``.
        """
        return TapestrySnapshot(knot_ids=list(self._live.keys()))

    def subscribe(self, callback: Callable[[Any], None]) -> object:
        """Register a callback invoked whenever a new knot is registered.

        Starts the background ``_listen_loop`` task if it is not already
        running.  The loop creates a dedicated pub/sub client subscribed to
        the registrations channel.

        Args:
            callback: Callable that accepts a single ``Knot`` argument.

        Returns:
            An opaque integer token for use with :meth:`unsubscribe`.
        """
        token = self._next_token
        self._next_token += 1
        self._subscribers[token] = callback
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.ensure_future(self._listen_loop())
        return token

    def unsubscribe(self, token: object) -> None:
        """Cancel a subscription.

        If the last subscriber is removed the background listen task is
        cancelled.

        Args:
            token: The token returned by :meth:`subscribe`.
        """
        self._subscribers.pop(token, None)  # type: ignore[arg-type]
        if not self._subscribers and self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None

    def _on_message(self, msg: Any, ctx: Any) -> None:
        """Pub/sub callback invoked for each message on the registrations channel.

        Decodes the knot id from the message, looks up the knot from the
        in-process dict, and dispatches to all subscribers.  Exceptions
        raised by callbacks are logged and suppressed.

        Args:
            msg: The pub/sub message object received from glide.
            ctx: Opaque context object passed through by glide (unused).
        """
        knot_id = msg.message.decode() if isinstance(msg.message, bytes) else msg.message
        knot = self._live.get(knot_id)
        if knot is None:
            return
        for cb in list(self._subscribers.values()):
            try:
                cb(knot)
            except Exception:
                _logger.warning(
                    "ValKeyStore: subscriber callback raised an exception for knot %r",
                    knot_id,
                    exc_info=True,
                )

    async def _listen_loop(self) -> None:
        """Hold a dedicated pub/sub connection until all subscribers cancel.

        Creates a new ``GlideClient`` configured with a pub/sub subscription
        to the registrations channel.  Falls back silently if ``glide`` is
        not installed or no config is available.
        """
        try:
            from glide import GlideClient, GlideClientConfiguration
            from glide.config import PubSubChannelModes, PubSubSubscriptions
        except ImportError:
            return

        if self._client._config is None:
            return

        subscriptions = PubSubSubscriptions(
            channels_and_patterns={PubSubChannelModes.Exact: {self._registrations_channel}},
            callback=self._on_message,
            context=None,
        )
        config = GlideClientConfiguration(
            self._client._config.addresses,
            pubsub_subscriptions=subscriptions,
        )
        sub_client = await GlideClient.create(config)
        try:
            while self._subscribers:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        finally:
            await sub_client.close()

    async def close(self) -> None:
        """Drain pending register tasks, cancel the listener, and close the client."""
        if self._pending_register_tasks:
            await asyncio.gather(*self._pending_register_tasks, return_exceptions=True)
            self._pending_register_tasks.clear()
        if self._listener_task is not None and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        await self._client.close()
