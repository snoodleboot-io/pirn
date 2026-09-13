"""``_SubQuestionSearch`` — search the store for one sub-question."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class _SubQuestionSearch(Knot):
    """Search the store for one sub-question and return its hits with provenance."""

    def __init__(
        self,
        *,
        sub_question: Knot | str,
        store: Knot | MemoryStore,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sub_question=sub_question, store=store, top_k=top_k, _config=_config, **kwargs
        )

    async def process(
        self,
        sub_question: str,
        store: MemoryStore,
        top_k: int,
        **_: Any,
    ) -> tuple[str, list[Mapping[str, Any]]]:
        """Search ``store`` for ``sub_question`` and return its hits.

        Args:
            sub_question: The sub-question to search for.
            store: The memory store to search.
            top_k: Maximum number of hits to fetch.

        Returns:
            A ``(sub_question, hits)`` pair.
        """
        hits = list(await store.search(sub_question, top_k=top_k))
        return sub_question, hits
