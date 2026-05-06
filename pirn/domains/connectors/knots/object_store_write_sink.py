"""``ObjectStoreWriteSink`` — a pirn :class:`Sink` that writes bytes to any
:class:`ObjectStore` backend at a configured key.

Algorithm:
    1. Validate that ``store`` is an :class:`ObjectStore`, ``key`` is a
       non-empty string, and ``body`` is ``bytes`` or ``bytearray``.
    2. Invoke ``await store.put(key, bytes(body))`` to write the payload.


References:
    - :class:`pirn.domains.connectors.object_store.ObjectStore`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.connectors.knots.object_store_knot import ObjectStoreKnot
from pirn.nodes.sink import Sink


class ObjectStoreWriteSink(Sink):
    """Sink that writes its ``body`` parent's output to ``key``."""

    def __init__(
        self,
        *,
        store: ObjectStoreKnot,
        key: Knot | str,
        body: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(store=store, key=key, body=body, _config=_config, **kwargs)

    async def process(self, store: ObjectStore, key: str, body: bytes, **_: Any) -> None:
        """Write the bytes payload to the configured object-store key.

        Args:
            store: The object store to write to.
            key: The key to write the object at.
            body: The bytes content to write to the configured key.

        Raises:
            TypeError: If store is not an ObjectStore or body is not bytes.
            ValueError: If key is empty.
        """
        if not isinstance(store, ObjectStore):
            raise TypeError(
                f"ObjectStoreWriteSink: store must be an ObjectStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(key, str) or not key:
            raise ValueError("ObjectStoreWriteSink: key must be a non-empty string")
        if not isinstance(body, (bytes, bytearray)):
            raise TypeError(
                f"ObjectStoreWriteSink: body must be bytes, got {type(body).__name__}"
            )
        await store.put(key, bytes(body))
