"""``MemoryRetriever`` — fetch a value by key from a :class:`MemoryStore`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore


class MemoryRetriever(Knot):
    """Retrieves the value previously stored under ``key``.

    Raises :class:`KeyError` when the key is not present so callers
    can fail loudly rather than silently treating ``None`` as a hit.
    """

    def __init__(
        self,
        *,
        key: Knot | str,
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "MemoryRetriever: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        super().__init__(
            key=key,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        key: str,
        store: MemoryStore,
        **_: Any,
    ) -> Mapping[str, Any]:
        if not isinstance(key, str) or not key:
            raise ValueError(
                "MemoryRetriever: key must be a non-empty string, "
                f"got {key!r}"
            )
        value = await store.retrieve(key)
        if value is None:
            raise KeyError(
                f"MemoryRetriever: no entry found for key {key!r}"
            )
        return value
