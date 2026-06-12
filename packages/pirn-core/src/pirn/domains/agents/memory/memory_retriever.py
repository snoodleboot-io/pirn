"""``MemoryRetriever`` — fetch a value by key from a :class:`MemoryStore`.

Algorithm:
    1. Receive the resolved ``key`` string and ``MemoryStore``.
    2. Validate input types at process time.
    3. Call ``store.retrieve(key)``.
    4. Raise ``KeyError`` if the value is ``None`` (key not found).
    5. Return the mapping.


References:
    - :class:`pirn.domains.agents.memory_store.MemoryStore`
"""

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
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        """Fetch the memory entry stored under key and return it as a mapping.

        Args:
            key: The non-empty string key to look up in the memory store.
            store: The memory store to retrieve the value from.

        Returns:
            The mapping stored under the given key.

        Raises:
            TypeError: If store is not a MemoryStore.
            ValueError: If key is not a non-empty string.
            KeyError: If no entry exists for the given key.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"MemoryRetriever: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(key, str) or not key:
            raise ValueError(f"MemoryRetriever: key must be a non-empty string, got {key!r}")
        value = await store.retrieve(key)
        if value is None:
            raise KeyError(f"MemoryRetriever: no entry found for key {key!r}")
        return value
