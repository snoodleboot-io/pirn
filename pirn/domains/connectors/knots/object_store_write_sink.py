"""``ObjectStoreWriteSink`` — a pirn :class:`Sink` that writes bytes to any
:class:`ObjectStore` backend at a configured key.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.nodes.sink import Sink


class ObjectStoreWriteSink(Sink):
    """Sink that writes its ``body`` parent's output to ``key``."""

    def __init__(
        self,
        *,
        store: ObjectStore,
        key: str,
        body: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, ObjectStore):
            raise TypeError(
                f"ObjectStoreWriteSink: store must be an ObjectStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(key, str) or not key:
            raise ValueError("ObjectStoreWriteSink: key must be a non-empty string")
        self._store = store
        self._key = key
        super().__init__(body=body, _config=_config, **kwargs)

    @property
    def store(self) -> ObjectStore:
        return self._store

    @property
    def key(self) -> str:
        return self._key

    async def process(self, body: bytes, **_: Any) -> None:
        if not isinstance(body, (bytes, bytearray)):
            raise TypeError(
                f"ObjectStoreWriteSink: body must be bytes, got {type(body).__name__}"
            )
        await self._store.put(self._key, bytes(body))
