"""``SemanticFactWriter`` — store extracted facts as searchable entries.

Inner stage knot used by :class:`SemanticMemoryPipeline`. Each fact is
stored under a deterministic key of the form ``"semantic:<sha1>"`` so
duplicate facts collapse to the same entry. Returns the number of
facts persisted.

Algorithm
---------
1. Validate inputs.
2. For each fact compute ``sha1(fact)`` as the deduplication key.
3. Call ``store.store("semantic:<digest>", payload)`` for each fact.
4. Return the count of facts written.

Math
----
No mathematical operations beyond SHA-1 hashing.

References
----------
None.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
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
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(facts=facts, store=store, _config=_config, **kwargs)

    async def process(
        self,
        facts: Sequence[str],
        store: MemoryStore,
        **_: Any,
    ) -> int:
        """Persist each fact under a deterministic hash key and return the count stored.

        Args:
            facts: The sequence of fact strings to persist.
            store: The MemoryStore to write each fact into.

        Returns:
            The number of facts stored.

        Raises:
            TypeError: If store is not a MemoryStore or any fact is not a string.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "SemanticFactWriter: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        count = 0
        now = datetime.now(UTC).isoformat()
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
            await store.store(key, payload)
            count += 1
        return count
