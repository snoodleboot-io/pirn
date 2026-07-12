"""``SummaryMemoryCompactor`` — compact older turns into a pinned summary.

The default :class:`~pirn_agents.context.compaction_strategy.CompactionStrategy`:
when fill exceeds the request's threshold, it evicts the oldest non-pinned items
(cheapest to lose, most redundant) until the context fits the budget, replaces
that block in place with a single **pinned** summary item produced by a
:class:`~pirn_agents.context.summarizer.Summarizer`, and — when a
``persist_key`` and memory store are present — writes the summary to the store
(the F27 summary-memory integration point). Pinned items are always retained.
"""

from __future__ import annotations

from pirn_agents.context.compaction_request import CompactionRequest
from pirn_agents.context.compaction_result import CompactionResult
from pirn_agents.context.compaction_strategy import CompactionStrategy
from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.summarizer import Summarizer
from pirn_agents.memory_store import MemoryStore


class SummaryMemoryCompactor(CompactionStrategy):
    """Threshold-triggered compaction that summarizes the oldest turns."""

    def __init__(
        self,
        *,
        summarizer: Summarizer,
        memory_store: MemoryStore | None = None,
    ) -> None:
        """Create the compactor.

        Args:
            summarizer: Strategy that compresses evicted content into a summary.
            memory_store: Optional F27 memory store; when set, produced summaries
                are persisted under the request's ``persist_key``.

        Raises:
            TypeError: If ``summarizer``/``memory_store`` are the wrong type.
        """
        if not isinstance(summarizer, Summarizer):
            raise TypeError(
                f"SummaryMemoryCompactor: summarizer must be a Summarizer, "
                f"got {type(summarizer).__name__}"
            )
        if memory_store is not None and not isinstance(memory_store, MemoryStore):
            raise TypeError(
                "SummaryMemoryCompactor: memory_store must be a MemoryStore or None, "
                f"got {type(memory_store).__name__}"
            )
        self._summarizer = summarizer
        self._memory_store = memory_store

    async def compact(self, request: CompactionRequest) -> CompactionResult:
        """Compact ``request`` per the :class:`CompactionStrategy` contract.

        Raises:
            TypeError: If ``request`` is not a CompactionRequest.
        """
        if not isinstance(request, CompactionRequest):
            raise TypeError(
                f"SummaryMemoryCompactor: request must be a CompactionRequest, "
                f"got {type(request).__name__}"
            )
        counter = request.counter
        items = request.items
        sizes = [counter.count(item.content) for item in items]
        tokens_before = sum(sizes)
        available = request.available_tokens()

        if tokens_before <= available * request.fill_threshold:
            return self._no_op(items, tokens_before)

        dropped = self._select_evictions(items, sizes, tokens_before, available)
        if not dropped:
            # Only pinned content remains; nothing can be compacted.
            return self._no_op(items, tokens_before)

        evicted_items = tuple(items[index] for index in dropped)
        summary = await self._summarizer.summarize([item.content for item in evicted_items])
        summary_item = ContextItem(
            content=summary,
            kind="summary",
            position=min(items[index].position for index in dropped),
            pinned=True,
        )
        retained = self._weave_summary(items, set(dropped), min(dropped), summary_item)
        tokens_after = sum(counter.count(item.content) for item in retained)

        await self._persist(request, summary, len(evicted_items))
        return CompactionResult(
            retained=retained,
            evicted=evicted_items,
            summary=summary,
            summary_item=summary_item,
            triggered=True,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )

    @staticmethod
    def _no_op(items: tuple[ContextItem, ...], tokens: int) -> CompactionResult:
        """Return an untriggered result leaving ``items`` unchanged."""
        return CompactionResult(
            retained=items,
            evicted=(),
            summary="",
            summary_item=None,
            triggered=False,
            tokens_before=tokens,
            tokens_after=tokens,
        )

    @staticmethod
    def _select_evictions(
        items: tuple[ContextItem, ...],
        sizes: list[int],
        tokens_before: int,
        available: int,
    ) -> list[int]:
        """Return indices of the oldest non-pinned items to evict to fit budget.

        Oldest-first by ``position`` (ties broken by original index); pinned
        items are never selected.
        """
        non_pinned = [index for index, item in enumerate(items) if not item.pinned]
        ordered = sorted(non_pinned, key=lambda index: (items[index].position, index))
        dropped: list[int] = []
        running = tokens_before
        for index in ordered:
            if running <= available:
                break
            dropped.append(index)
            running -= sizes[index]
        return dropped

    @staticmethod
    def _weave_summary(
        items: tuple[ContextItem, ...],
        dropped: set[int],
        insert_at: int,
        summary_item: ContextItem,
    ) -> tuple[ContextItem, ...]:
        """Rebuild the item list, replacing the evicted block with the summary.

        The summary takes the slot of the earliest evicted item so it sits where
        the compacted history was; all other retained items keep their order.
        """
        retained: list[ContextItem] = []
        for index, item in enumerate(items):
            if index in dropped:
                if index == insert_at:
                    retained.append(summary_item)
                continue
            retained.append(item)
        return tuple(retained)

    async def _persist(self, request: CompactionRequest, summary: str, evicted_count: int) -> None:
        """Write the summary to the memory store when configured."""
        if self._memory_store is None or request.persist_key is None:
            return
        await self._memory_store.store(
            request.persist_key,
            {"summary": summary, "evicted_count": evicted_count},
        )
