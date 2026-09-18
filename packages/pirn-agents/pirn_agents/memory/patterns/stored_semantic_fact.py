"""``StoredSemanticFact`` — persist one semantic fact, as its own knot.

Per-fact knot of
:class:`~pirn_agents.memory.patterns.semantic_fact_writer.SemanticFactWriter`.
The facts in a batch are independent of one another, so the writer runs one
``StoredSemanticFact`` per fact inside a nested run
(:class:`~pirn.nodes.nested_run_knot.NestedRunKnot`) joined by an
:class:`~pirn.nodes.aggregator.Aggregator`: every store write gets its own
lineage row, ``Result`` and admission slot, and the batch is written
concurrently under the enclosing run's caps instead of one ``await`` at a time
inside a single ``process()`` (PIR-873).

Algorithm:
    1. Content-address the fact through
       :class:`~pirn.core.content_hasher.ContentHasher` and prefix the digest
       with ``semantic:`` — two writes of the same fact collapse onto one
       entry.
    2. Write ``{"fact", "stored_at"}`` under that key.
    3. Return the key.

Internal API.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class StoredSemanticFact(Knot):
    """Persist one fact under its content-addressed key and return that key."""

    def __init__(
        self,
        *,
        fact: Knot | str,
        store: Knot | MemoryStore,
        stored_at: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(fact=fact, store=store, stored_at=stored_at, _config=_config, **kwargs)

    async def process(self, fact: str, store: MemoryStore, stored_at: str, **_: Any) -> str:
        """Write ``fact`` under its content-addressed key and return the key.

        Args:
            fact: The fact text to persist.
            store: The store to write into.
            stored_at: ISO-8601 timestamp recorded with the fact, read from the
                writer's injected clock so a deterministic run reproduces it.

        Returns:
            The key the fact was written under.

        Raises:
            TypeError: If ``fact`` is not a string.
        """
        if not isinstance(fact, str):
            raise TypeError(f"StoredSemanticFact: fact must be a string, got {type(fact).__name__}")
        key = f"semantic:{ContentHasher.hash(fact)}"
        await store.store(key, {"fact": fact, "stored_at": stored_at})
        return key
