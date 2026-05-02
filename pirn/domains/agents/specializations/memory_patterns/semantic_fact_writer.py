"""``SemanticFactWriter`` — store extracted facts as searchable entries.

Inner stage knot used by :class:`SemanticMemoryPipeline`. Each fact is
stored under a deterministic key of the form ``"semantic:<sha1>"`` so
duplicate facts collapse to the same entry. Returns the number of
facts persisted.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore


class SemanticFactWriter(Knot):
    """Persists each fact in ``facts`` to a :class:`MemoryStore`."""

    def __init__(
        self,
        *,
        facts: Knot | Sequence[str],
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "SemanticFactWriter: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        self._store = store
        super().__init__(facts=facts, _config=_config, **kwargs)

    async def process(
        self,
        facts: Sequence[str],
        **_: Any,
    ) -> int:
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for fact in facts:
            if not isinstance(fact, str):
                raise TypeError(
                    "SemanticFactWriter: every fact must be a string, "
                    f"got {type(fact).__name__}"
                )
            digest = hashlib.sha1(fact.encode("utf-8")).hexdigest()
            key = f"semantic:{digest}"
            payload: dict[str, Any] = {
                "fact": fact,
                "stored_at": now,
            }
            await self._store.store(key, payload)
            count += 1
        return count
