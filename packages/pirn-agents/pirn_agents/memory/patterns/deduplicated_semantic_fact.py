"""``DeduplicatedSemanticFact`` — record one fact unless it is already on record.

One knot per candidate fact, so each dedup read and each write has its own
``Result``, retry, timeout and lineage row rather than being one turn of a
Python loop the run cannot see (Rule 11; PIR-874) — the shape
:class:`~pirn_agents.memory.patterns.stored_semantic_fact.StoredSemanticFact`
already uses for unconditional writes.

Dedup is per fact and therefore safe to run concurrently: a fact's identity is
``ContentHasher.hash(fact)``, so two *different* facts never contend for the
same key. Two *identical* facts would, which is why
:class:`~pirn_agents.memory.patterns.semantic_memory_upsert.SemanticMemoryUpsert`
collapses repeats out of one extraction before it builds these knots.

Internal API. See ``semantic_memory_upsert.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.management.memory_provenance import MemoryProvenance
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore


class DeduplicatedSemanticFact(Knot):
    """Write one fact as a typed ``MemoryRecord``, unless its identity already holds one."""

    def __init__(
        self,
        *,
        fact: Knot | str,
        namespace: Knot | str,
        store: Knot | KeyedLineageStore,
        stored_at: Knot | datetime,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            fact=fact,
            namespace=namespace,
            store=store,
            stored_at=stored_at,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        fact: str,
        namespace: str,
        store: KeyedLineageStore,
        stored_at: datetime,
        **_: Any,
    ) -> str | None:
        """Upsert ``fact`` and return the key it was written under, or ``None``.

        Args:
            fact: The candidate fact text; its content hash is its identity.
            namespace: The store namespace the fact belongs in.
            store: The ``KeyedLineageStore`` to read the dedup signal from and
                write to.
            stored_at: The timestamp the record is stamped with, passed in so
                every fact of one extraction shares it.

        Returns:
            The key the fact was written under, or ``None`` when it was already
            on record. A key rather than a ``bool`` because a knot whose output
            is a bare verdict is core's ``Check`` role, and this one does work.
        """
        key = ContentHasher.hash(fact)
        # ``get`` and not ``latest_output_hash``: a deleted fact still has a
        # lineage row and therefore still has a hash, so the hash test read
        # every tombstoned fact as "already recorded" and the fact could
        # never be written again (PIR-873).  ``get`` is the one read that
        # treats a tombstone as absent.
        if await store.get(namespace=namespace, key=key) is not None:
            return None
        record = MemoryRecord(
            id=f"fact:{key}",
            kind="semantic",
            content=fact,
            provenance=MemoryProvenance(source="semantic_memory_upsert", timestamp=stored_at),
            created_at=stored_at,
        )
        await store.put(namespace=namespace, key=key, value=record.to_payload())
        return key
