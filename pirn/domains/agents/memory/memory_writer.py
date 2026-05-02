"""``MemoryWriter`` — persist a (key, value) entry into a :class:`MemoryStore`."""

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
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "MemoryWriter: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
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
        if not isinstance(key, str) or not key:
            raise ValueError(
                "MemoryWriter: key must be a non-empty string, "
                f"got {key!r}"
            )
        if not isinstance(value, Mapping):
            raise TypeError(
                "MemoryWriter: value must be a Mapping, "
                f"got {type(value).__name__}"
            )
        await store.store(key, value)
        return key
