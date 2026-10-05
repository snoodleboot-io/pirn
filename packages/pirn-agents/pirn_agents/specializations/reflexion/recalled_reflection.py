"""``RecalledReflection`` — read back one reflection an earlier iteration wrote.

One knot per key, declared inside the iteration's own tapestry, so each read
has its own ``Result``, retry, timeout and lineage row rather than being one
turn of a Python loop inside ``astep`` that the run cannot see (Rule 11;
PIR-874).

A key with nothing behind it, or whose entry carries no ``text`` string, yields
``None`` and the aggregator feeding the actor drops it — the loop has always
tolerated a missing reflection rather than failing the iteration for it.

Internal API. See ``reflexion_loop.py``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class RecalledReflection(Knot):
    """Read one reflection's text out of a ``MemoryStore``, or report its absence."""

    def __init__(
        self,
        *,
        memory: Knot | MemoryStore,
        key: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(memory=memory, key=key, _config=_config, **kwargs)

    async def process(self, memory: MemoryStore, key: str, **_: Any) -> str | None:
        """Return the reflection text stored under ``key``, or ``None``.

        Args:
            memory: The store earlier iterations wrote their reflections to.
            key: The key to read.

        Returns:
            The reflection text, or ``None`` when the key is absent or holds no
            ``text`` string.
        """
        entry = await memory.retrieve(key)
        if entry is None:
            return None
        text = entry.get("text")
        return text if isinstance(text, str) else None
