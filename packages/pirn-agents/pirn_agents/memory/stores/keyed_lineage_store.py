# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``KeyedLineageStore`` — a caller-chosen key is a knot id, not a KV slot.

ADR "agents speaks core" WS3 part 4. Retires the reason
:class:`~pirn_agents.memory.stores.data_store_memory_store.DataStoreMemoryStore`
hashed a caller's logical key into a content hash and ``MemoryStoreKeyIndex``
existed at all: a keyed identity does not need a hashed slot in a key-value
table when the engine already gives every knot a stable, queryable identity.

The mapping:

* **write** — a caller-chosen ``f"{namespace}:{key}"`` becomes a
  ``KnotConfig.id``; :meth:`put` runs it as a single-knot ``Tapestry`` (the
  same shape :class:`~pirn_agents.determinism.cassette_recorder.CassetteRecorder`
  uses for a cassette key). The engine content-addresses the value into
  ``DataStore`` and records one ``KnotLineage`` row — no separate keyed write.
* **read** — "the current value under this key" is
  ``RunHistory.query_latest_lineage_by_knot_id(f"{namespace}:{key}")`` (core's
  keyed-identity seam, ADR WS3 part 4) → ``DataStore.get(output_hash)``.
  Every write is a new row, so the full history under a key is never lost —
  ``get`` reads the newest one.

What this does **not** give you, and why:

* **Delete** has no lineage equivalent (there is no "unrecord a run"), so
  :meth:`delete` writes a tombstone value instead — :meth:`get` treats it as
  absent. A deleted-then-rewritten key still has its full history in
  ``RunHistory`` for anyone who wants it; ordinary readers just see "absent,
  then present again".
* **Enumeration** ("every key ever written under a namespace") has no
  ``RunHistory`` query either — lineage is looked up by an exact knot id, not
  listed by prefix. A caller that needs to enumerate keys still needs an
  explicit index (this was the gap ``MemoryStoreKeyIndex`` filled for its one
  consumer, ``PersistedSessionStore``, itself a deprecated shim deleted with
  it in PIR-864).
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.determinism._thunk_source import _ThunkSource


class KeyedLineageStore(PirnOpaqueValue):
    """Read/write a caller-keyed identity as a knot id, backed by lineage.

    Mixes in :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` (the same
    treatment :class:`~pirn_agents.memory.stores.memory_store.MemoryStore`
    gets) so a knot can declare it directly as a typed ``process()``
    parameter: IO validation only needs ``isinstance(value, cls)``, not a
    descent into the wrapped ``RunHistory``/``DataStore``.
    """

    #: Sentinel written by :meth:`delete`; :meth:`get` treats a value with
    #: this shape as absent rather than returning it.
    _tombstone: ClassVar[Mapping[str, Any]] = {"__keyed_lineage_store_deleted__": True}

    #: Characters :meth:`_escape_identity_component` passes through
    #: unescaped. Deliberately excludes ``.`` and ``:`` even though
    #: ``KnotConfig.id`` allows them — both are meaningful to the escaping
    #: scheme itself (the escape leader and the namespace/key separator,
    #: respectively), so both must always be escaped when they appear
    #: *inside* a caller's namespace or key.
    _identity_safe_chars: ClassVar[frozenset[str]] = frozenset(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    )

    def __init__(self, *, history: RunHistory, data_store: DataStore) -> None:
        """Bind the store to the ``RunHistory``/``DataStore`` pair it reads and writes.

        Raises:
            TypeError: If ``history`` is not a ``RunHistory`` or ``data_store``
                is not a ``DataStore``.
        """
        if not isinstance(history, RunHistory):
            raise TypeError(
                f"KeyedLineageStore: history must be a RunHistory, got {type(history).__name__}"
            )
        if not isinstance(data_store, DataStore):
            raise TypeError(
                f"KeyedLineageStore: data_store must be a DataStore, "
                f"got {type(data_store).__name__}"
            )
        self._history = history
        self._data_store = data_store

    @property
    def history(self) -> RunHistory:
        return self._history

    @property
    def data_store(self) -> DataStore:
        return self._data_store

    @classmethod
    def _escape_identity_component(cls, component: str) -> str:
        """Escape ``component`` into the charset a ``KnotConfig.id`` allows.

        Every byte outside :attr:`_identity_safe_chars` becomes ``.xx`` (its
        lowercase hex value, UTF-8 encoded) — including ``.`` and ``:`` — so
        the output contains a bare ``.`` or ``:`` only where this method or
        :meth:`identity` put one, never as a leftover from the caller's own
        text.
        """
        escaped: list[str] = []
        for char in component:
            if char in cls._identity_safe_chars:
                escaped.append(char)
            else:
                escaped.extend(f".{byte:02x}" for byte in char.encode("utf-8"))
        return "".join(escaped)

    @classmethod
    def identity(cls, namespace: str, key: str) -> str:
        """Return the knot id a ``(namespace, key)`` pair maps to.

        ``KnotConfig.id`` only allows ``[a-zA-Z0-9_.:-]``, but a caller's key
        is arbitrary — filesystem-hostile keys (``"../../etc/passwd"``,
        ``"a/b/c"``, spaces, unicode, ``"?*<>|"``) are exactly what a
        MemoryStore consumer already passes today. Each component is escaped
        independently before being joined: any byte outside
        ``[a-zA-Z0-9_-]`` — including a literal ``.`` or ``:``, so an escape
        sequence can never be mistaken for one the caller wrote, and a colon
        inside one component can never be mistaken for the namespace/key
        separator this method inserts — becomes ``.xx`` (its lowercase hex
        byte, UTF-8 encoded). A plain identifier (``"ns"``, ``"k1"``) round
        trips unescaped, so existing readable ids are unaffected.

        Raises:
            ValueError: If ``namespace`` or ``key`` is empty.
        """
        if not namespace:
            raise ValueError("KeyedLineageStore.identity: namespace must be non-empty")
        if not key:
            raise ValueError("KeyedLineageStore.identity: key must be non-empty")
        return f"{cls._escape_identity_component(namespace)}:{cls._escape_identity_component(key)}"

    async def put(self, *, namespace: str, key: str, value: Any) -> str:
        """Write ``value`` as the current value under ``(namespace, key)``.

        Args:
            namespace: Logical grouping for the key (mirrors
                ``DataStoreMemoryStore``'s old namespace parameter).
            key: The caller-chosen identity within ``namespace``.
            value: Any value the engine can content-address (a mapping is
                recommended — it hashes deterministically and every existing
                keyed caller already speaks in mappings).

        Returns:
            The knot id the value was recorded under (``f"{namespace}:{key}"``).
        """
        identity = self.identity(namespace, key)

        with Tapestry(history=self._history, data_store=self._data_store) as tapestry:
            _ThunkSource(_config=KnotConfig(id=identity)).bind(
                functools.partial(KeyedLineageStore._resolved, value)
            )
            await tapestry.run(RunRequest())
        return identity

    async def get(self, *, namespace: str, key: str) -> Any | None:
        """Return the current value under ``(namespace, key)``, or ``None``.

        "Current" is the newest recorded write —
        ``RunHistory.query_latest_lineage_by_knot_id`` — not the last one this
        process happened to make; a durable, shared ``history``/``data_store``
        sees writes from any process.

        Returns:
            The value, ``None`` if the key was never written (or was
            :meth:`delete`\\ d and never rewritten), or ``None`` if the
            backend evicted it (see ``DataStore.get``'s ``KeyError`` note) —
            a keyed read reports absence the same way for both.
        """
        identity = self.identity(namespace, key)
        row = await self._history.query_latest_lineage_by_knot_id(identity)
        if row is None or row.outcome != "ok" or row.output_hash is None:
            return None
        try:
            value = await self._data_store.get(row.output_hash)
        except KeyError:
            return None
        return None if value == type(self)._tombstone else value

    async def latest_output_hash(self, *, namespace: str, key: str) -> str | None:
        """Return the content hash of the current value under ``(namespace, key)``.

        For a caller that wants to know "did the value change" without
        fetching it — compare a candidate's own
        ``pirn.core.content_hasher.ContentHasher.hash(candidate)`` against this. ``None``
        when the key was never written or its outcome was not ``"ok"``; a
        tombstone still has a real hash (of :attr:`_tombstone`), same as any
        other value — a caller checking for "was this deleted" should use
        :meth:`get` instead.
        """
        identity = self.identity(namespace, key)
        row = await self._history.query_latest_lineage_by_knot_id(identity)
        if row is None or row.outcome != "ok":
            return None
        return row.output_hash

    async def delete(self, *, namespace: str, key: str) -> None:
        """Write a tombstone for ``(namespace, key)`` — :meth:`get` reads it as absent.

        Deleting an already-absent key is a no-op write (a tombstone over a
        tombstone) — cheap, and harmless since :meth:`get` treats both the
        same.
        """
        await self.put(namespace=namespace, key=key, value=type(self)._tombstone)

    @staticmethod
    async def _resolved(value: Any) -> Any:
        """Return ``value`` — bound with ``functools.partial`` as the write's zero-arg thunk."""
        return value
