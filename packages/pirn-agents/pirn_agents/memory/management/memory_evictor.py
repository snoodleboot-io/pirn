"""``MemoryEvictor`` — apply an eviction policy and forget the selected records.

The S2 write-side knot. Given the candidate records the caller listed from a
store, an eviction policy, and a store, it asks the policy which records to drop
and forgets each, returning the evicted ids. It reads only the batch it is
handed and writes only through
:meth:`~pirn_agents.memory.stores.memory_store.MemoryStore.forget` — the
``MemoryStore`` read/write contract is untouched, so eviction composes with F17
compaction and any concrete store backend.

One knot per victim (PIR-873). The evictions are independent of one another, so
they are a fan-out and not a sequence: this is a
:class:`~pirn.nodes.nested_run_knot.NestedRunKnot` whose ``process()`` builds one
:class:`~pirn_agents.memory.management.forgotten_memory_record.ForgottenMemoryRecord`
per victim under an :class:`~pirn.nodes.aggregator.Aggregator` and runs them
through ``_run_inner``. Every ``forget`` then has its own lineage row,
``Result``, retry and admission slot — so a single failing eviction is
attributable instead of being one opaque failure for the batch — and the batch
proceeds concurrently under the enclosing run's caps rather than one ``await`` at
a time. As a container this knot holds no admission slot of its own, so it may
not declare a ``concurrency_group``. Evicting nothing starts no inner run.

Algorithm:
    1. Ask the policy which records to drop, and type-check what it returned.
    2. Build one ``ForgottenMemoryRecord`` per victim, joined by an
       ``Aggregator`` that orders the ids by the policy's selection order.
    3. Run them as a nested run and return the evicted ids.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.memory.management.forgotten_memory_record import ForgottenMemoryRecord
from pirn_agents.memory.management.memory_eviction_policy import MemoryEvictionPolicy
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.stores.memory_store import MemoryStore


class MemoryEvictor(NestedRunKnot):
    """Evicts policy-selected records from a :class:`MemoryStore`, one knot per record."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[MemoryRecord],
        policy: Knot | MemoryEvictionPolicy,
        store: Knot | MemoryStore,
        now: Knot | datetime,
        capacity: Knot | int | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            policy=policy,
            store=store,
            now=now,
            capacity=capacity,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[MemoryRecord],
        policy: MemoryEvictionPolicy,
        store: MemoryStore,
        now: datetime,
        capacity: int | None = None,
        **_: Any,
    ) -> tuple[str, ...]:
        """Evict the records ``policy`` selects and return their ids.

        Args:
            records: The candidate records to consider.
            policy: The eviction policy deciding what to drop.
            store: The store to forget evicted records from.
            now: The timezone-aware reference time passed to the policy.
            capacity: Optional retain-count budget forwarded to the policy.

        Returns:
            The ids of the evicted records, in the policy's selection order.

        Raises:
            TypeError: If ``policy`` is not a MemoryEvictionPolicy or ``store`` is
                not a MemoryStore.
            SubTapestryError: If any eviction failed.
        """
        victims = policy.select(tuple(records), now=now, capacity=capacity)
        victim_ids: list[str] = []
        for record in victims:
            if not isinstance(record, MemoryRecord):
                raise TypeError(
                    f"MemoryEvictor: policy returned a non-record {type(record).__name__}"
                )
            victim_ids.append(record.data.id)
        if not victim_ids:
            return ()
        with Tapestry() as inner:
            store_node = Parameter(
                "store", MemoryStore, default=store, _config=KnotConfig(id="store")
            )
            per_victim: dict[str, Knot] = {
                f"evicted_{index}": ForgottenMemoryRecord(
                    record_id=record_id,
                    store=store_node,
                    _config=KnotConfig(id=f"evicted_{index}"),
                )
                for index, record_id in enumerate(victim_ids)
            }
            Aggregator(
                combine=MemoryEvictor._in_selection_order,
                _config=KnotConfig(id="evicted"),
                **per_victim,
            )
        run = await self._run_inner(inner)
        return run.outputs["evicted"]

    @staticmethod
    def _in_selection_order(**ids: str) -> tuple[str, ...]:
        """Order the evicted ids by their ``evicted_<index>`` key."""
        return tuple(ids[f"evicted_{index}"] for index in range(len(ids)))
