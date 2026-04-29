"""ValKey backend.

Provides ``ValKeyStore`` (TapestryStore) and ``ValKeyDataStore``
(DataStore) backed by ValKey via the async-native ``valkey-glide``
client.

ValKey shines as a ``DataStore``: content-addressed values are exactly
the workload it's designed for — string keys, opaque values, optional
TTLs, fast O(1) GET/SET, cluster-aware sharding for free.

It can also serve as a ``TapestryStore`` for distributed deployments
where multiple processes register knots into a shared workspace.  The
store keeps live knot references locally per-process and uses ValKey
only for the cross-process snapshot (which knot ids exist).

A separate ``RunHistory`` over ValKey is *not* provided here — lineage
queries are analytical (range scans, joins) and ValKey isn't tuned for
that.  Use ``PostgresHistory`` or ``DuckDBHistory`` and pair them with
``ValKeyDataStore`` for the values.
"""

from __future__ import annotations

import asyncio
import json
import pickle
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pirn.backends import TapestrySnapshot

if TYPE_CHECKING:
    from pirn.core.knot import Knot


# ------------------------------------------------------------ Lazy client


class _LazyClient:
    """Wraps either an injected client (test / sharing) or a config."""

    def __init__(self, client: Any = None, config: Any = None) -> None:
        if client is None and config is None:
            raise TypeError("provide either client= or config=")
        self._client = client
        self._config = config

    async def get(self) -> Any:
        if self._client is None:
            try:
                from glide import GlideClient
            except ImportError as exc:
                raise ImportError(
                    "ValKey backends require valkey-glide; install via `pip install pirn[valkey]`"
                ) from exc
            self._client = await GlideClient.create(self._config)
        return self._client

    async def close(self) -> None:
        if self._client is not None and self._config is not None:
            await self._client.close()
            self._client = None


# ----------------------------------------------------------- Store


class ValKeyStore:
    """``TapestryStore`` backed by ValKey.

    Live knot references are kept in-process; ValKey holds a sorted set
    of knot ids and a hash per knot containing its class name, config
    JSON, and parent map.  Cross-process queries can read the snapshot
    without touching live Python objects (which couldn't cross process
    boundaries anyway).
    """

    _IDS_KEY = "pirn:tapestry:ids"
    _KNOT_KEY_PREFIX = "pirn:tapestry:knot:"

    _REGISTRATIONS_CHANNEL = "pirn:tapestry:registrations"

    def __init__(self, *, client: Any = None, config: Any = None) -> None:
        self._client = _LazyClient(client=client, config=config)
        self._live: dict[str, Knot] = {}
        self._pending_register_tasks: list[Any] = []
        self._subscribers: dict[int, Callable[[Any], None]] = {}
        self._next_token: int = 0
        self._listener_task: asyncio.Task[None] | None = None

    async def aregister(self, knot: Knot) -> None:
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
        knot_key = f"{self._KNOT_KEY_PREFIX}{knot.knot_id}"

        # Store as a hash; track membership in a set for ordered listing.
        await client.hset(
            knot_key,
            {
                "knot_class": knot_class,
                "config_json": config_json,
                "parents_json": parents_json,
            },
        )
        await client.sadd(self._IDS_KEY, [knot.knot_id])
        if self._subscribers:
            await client.publish(self._REGISTRATIONS_CHANNEL, knot.knot_id)

    def register(self, knot: Knot) -> None:
        """Synchronous registration — best-effort only.

        The live cache is updated immediately so same-process ``get()``
        works at once, but the ValKey write is fire-and-forget.  If the
        process crashes before the write completes, the knot will be
        absent from ValKey on restart.

        **Production recommendation:** prefer ``await store.aregister(knot)``
        directly, or call ``await store.close()`` before process shutdown
        to drain any pending writes.  ``register()`` is provided for
        convenience in sync contexts (e.g. a ``with Tapestry()`` block)
        where awaiting is not possible.
        """
        import asyncio

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
        # Inside a running loop: schedule but don't block; the live
        # cache makes get() / all() / snapshot() work immediately.
        # Holding a strong reference to the task prevents the GC from
        # collecting it before the async write completes.
        self._pending_register_tasks.append(asyncio.ensure_future(self.aregister(knot)))

    async def close(self) -> None:
        """Drain any pending background register tasks and release resources.

        Call this when tearing down the store to ensure all fire-and-forget
        ``register()`` calls have flushed to ValKey before the process exits.
        Safe to call multiple times.
        """
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

    def get(self, knot_id: str) -> Knot | None:
        return self._live.get(knot_id)

    def all(self) -> list[Knot]:
        return list(self._live.values())

    def snapshot(self) -> TapestrySnapshot:
        return TapestrySnapshot(knot_ids=list(self._live.keys()))

    def subscribe(self, callback: Callable[[Any], None]) -> object:
        """Register a callback fired for each newly registered knot.

        Starts a background pubsub listener task on first subscriber.
        Note: callbacks receive the live ``Knot`` from the in-process
        cache — cross-process extension is not yet supported.
        """
        token = self._next_token
        self._next_token += 1
        self._subscribers[token] = callback
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.ensure_future(self._listen_loop())
        return token

    def unsubscribe(self, token: object) -> None:
        self._subscribers.pop(token, None)  # type: ignore[arg-type]
        if not self._subscribers and self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None

    async def _listen_loop(self) -> None:
        """Subscribe to the registrations pubsub channel; dispatch to callbacks.

        ValKey-Glide pubsub requires a separate client configured with
        subscriptions at creation time.  We build one lazily here; it
        cannot be shared with the write client.
        """
        try:
            from glide import (
                GlideClient,
                GlideClientConfiguration,
            )
            from glide.config import (
                PubSubChannelModes,
                PubSubSubscriptions,
            )
        except ImportError:
            return

        # We need the host/port from the existing client config — if an
        # injected client was used (tests), we can't build a subscriber
        # client and fall back to a no-op.
        if self._client._config is None:
            return

        def _msg_callback(msg: Any, ctx: Any) -> None:
            knot_id = msg.message.decode() if isinstance(msg.message, bytes) else msg.message
            knot = self._live.get(knot_id)
            if knot is None:
                return
            for cb in list(self._subscribers.values()):
                try:
                    cb(knot)
                except Exception:
                    pass

        subscriptions = PubSubSubscriptions(
            channels_and_patterns={PubSubChannelModes.Exact: {self._REGISTRATIONS_CHANNEL}},
            callback=_msg_callback,
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


# ----------------------------------------------------------- DataStore


class ValKeyDataStore:
    """``DataStore`` backed by ValKey.

    Values are pickled and stored under their content hash.  This is
    the right shape for ValKey: small-to-medium opaque blobs with O(1)
    GET/SET, optional TTL, and (in cluster mode) automatic sharding.

    Why pickle and not JSON?  Knot outputs may be arbitrary Python
    objects (Pydantic models, dataclasses, custom types), and the data
    store is internal — we control both writers and readers.  For
    cross-language scenarios users can swap in a JSON-only data store
    and accept the constraint.
    """

    _PREFIX = "pirn:data:"

    def __init__(
        self,
        *,
        client: Any = None,
        config: Any = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self._client = _LazyClient(client=client, config=config)
        self._ttl = ttl_seconds

    def _key(self, content_hash: str) -> str:
        return f"{self._PREFIX}{content_hash}"

    async def put(self, content_hash: str, value: Any) -> None:
        from glide import ExpirySet, ExpiryType

        client = await self._client.get()
        payload = pickle.dumps(value)
        if self._ttl is not None:
            expiry = ExpirySet(ExpiryType.SEC, self._ttl)
            await client.set(self._key(content_hash), payload, expiry=expiry)
        else:
            await client.set(self._key(content_hash), payload)

    async def get(self, content_hash: str) -> Any:
        client = await self._client.get()
        payload = await client.get(self._key(content_hash))
        if payload is None:
            raise KeyError(content_hash)
        return pickle.loads(payload)

    async def has(self, content_hash: str) -> bool:
        client = await self._client.get()
        return bool(await client.exists([self._key(content_hash)]))

    async def scrub(self, content_hash: str) -> None:
        client = await self._client.get()
        await client.delete([self._key(content_hash)])

    async def close(self) -> None:
        await self._client.close()
