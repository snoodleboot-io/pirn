"""``MemoryWriter`` — persist a (key, value) entry into a :class:`MemoryStore`.

Algorithm:
    1. Receive the resolved ``key``, ``value``, and ``MemoryStore``.
    2. Validate input types at process time.
    3. Call ``store.store(key, value)`` to persist.
    4. Return the key so downstream knots can address the just-written entry.


References:
    - :class:`pirn.domains.agents.memory_store.MemoryStore`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore


class MemoryWriter(Knot):
    """Writes ``(key, value)`` to a :class:`MemoryStore` and returns ``key``.

    Returning the key (rather than ``None``) lets downstream knots
    address the just-written entry without re-deriving it. Both
    ``key`` and ``value`` may be supplied as upstream :class:`Knot`s
    or as plain literals.
    """

    def __init__(
        self,
        *,
        key: Knot | str,
        value: Knot | Mapping[str, Any],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            key=key,
            value=value,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        key: str,
        value: Mapping[str, Any],
        store: MemoryStore,
        **_: Any,
    ) -> str:
        """Persist the value mapping under key in the store and return the key.

        Args:
            key: The non-empty string key to store the value under.
            value: The mapping to persist in the store.
            store: The memory store to write to.

        Returns:
            The key the value was stored under.

        Raises:
            TypeError: If store is not a MemoryStore or value is not a Mapping.
            ValueError: If key is not a non-empty string.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"MemoryWriter: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(key, str) or not key:
            raise ValueError(f"MemoryWriter: key must be a non-empty string, got {key!r}")
        if not isinstance(value, Mapping):
            raise TypeError(f"MemoryWriter: value must be a Mapping, got {type(value).__name__}")
        await store.store(key, value)
        return key
