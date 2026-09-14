"""``ChunkStoreWrite`` — persist one embedded chunk under its store key.

Internal per-chunk knot for
:class:`~pirn_agents.specializations.document_processing._chunk_embedder_store.ChunkEmbedderStore`'s
fan-out (PIR-867): each chunk's write is independent of every other chunk's,
so it is one node per chunk rather than a hand-rolled ``asyncio.gather`` over
bare coroutines.

Internal API.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class ChunkStoreWrite(Knot):
    """Persist one chunk's embedding payload under ``key`` in ``store``."""

    def __init__(
        self,
        *,
        key: Knot | str,
        payload: Knot | Mapping[str, Any],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(key=key, payload=payload, store=store, _config=_config, **kwargs)

    async def process(
        self, key: str, payload: Mapping[str, Any], store: MemoryStore, **_: Any
    ) -> str:
        """Persist ``payload`` under ``key`` and return the key written."""
        await store.store(key, payload)
        return key
