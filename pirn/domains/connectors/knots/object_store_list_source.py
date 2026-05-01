"""``ObjectStoreListSource`` — a pirn :class:`Source` that lists keys under
a prefix in any :class:`ObjectStore` backend.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.nodes.source import Source


class ObjectStoreListSource(Source):
    """Source that lists keys under a fixed ``prefix`` in lexicographic order."""

    def __init__(
        self,
        *,
        store: ObjectStore,
        prefix: str = "",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, ObjectStore):
            raise TypeError(
                f"ObjectStoreListSource: store must be an ObjectStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(prefix, str):
            raise TypeError("ObjectStoreListSource: prefix must be a string")
        self._store = store
        self._prefix = prefix
        super().__init__(_config=_config, **kwargs)

    @property
    def store(self) -> ObjectStore:
        return self._store

    @property
    def prefix(self) -> str:
        return self._prefix

    async def process(self, **_: Any) -> list[str]:
        keys: list[str] = []
        async for key in await self._store.list(self._prefix):
            keys.append(key)
        return keys
