"""``SemanticFactWriter`` — store extracted facts as searchable entries.

Inner stage knot used by :class:`SemanticMemoryPipeline`. Each fact is stored
under a content-addressed key of the form ``"semantic:<ContentHasher hash>"`` so
duplicate facts collapse to the same entry. Returns the number of facts
persisted.

One knot per fact (PIR-873). The facts in a batch are independent, so the writes
are a fan-out and not a sequence: this is a
:class:`~pirn.nodes.nested_run_knot.NestedRunKnot` whose ``process()`` builds one
:class:`~pirn_agents.memory.patterns.stored_semantic_fact.StoredSemanticFact` per
fact under an :class:`~pirn.nodes.aggregator.Aggregator` and runs them through
``_run_inner``. Every write then has its own lineage row, ``Result``, retry and
admission slot, and the batch proceeds concurrently under the enclosing run's
caps — where the previous ``for fact in facts: await store.store(...)`` loop was
invisible to the engine, serialised regardless of the run's concurrency, and
reported one outcome for the whole batch. As a container this knot holds no
admission slot of its own (its writes take them), so it may not declare a
``concurrency_group``. An empty batch starts no inner run at all.

Algorithm
---------
1. Validate that every fact is a string, and read one ``stored_at`` from the
   injected :class:`~pirn_agents.determinism.clock.Clock` so the whole batch
   shares a timestamp a deterministic run can reproduce.
2. Build one ``StoredSemanticFact`` per fact, each keyed
   ``semantic:<ContentHasher.hash(fact)>``, joined by an ``Aggregator``.
3. Run them as a nested run and return the number of keys written.

Math
----
``key = "semantic:" + ContentHasher.hash(fact)`` — the workspace's one
content-addressing seam (canonical serialisation, sha256), in place of a bare
``hashlib.sha1`` of the UTF-8 bytes.

References
----------
None.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.determinism.clock import Clock
from pirn_agents.determinism.system_clock import SystemClock
from pirn_agents.memory.memory_writer_base import MemoryWriterBase
from pirn_agents.memory.patterns.stored_semantic_fact import StoredSemanticFact
from pirn_agents.memory.stores.memory_store import MemoryStore


class SemanticFactWriter(MemoryWriterBase, NestedRunKnot):
    """Persists each fact in ``facts`` to a :class:`MemoryStore`, one knot per fact."""

    def __init__(
        self,
        *,
        facts: Knot | Sequence[str],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        clock: Knot | Clock | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(facts=facts, store=store, clock=clock, _config=_config, **kwargs)

    async def process(
        self,
        facts: Sequence[str],
        store: MemoryStore,
        clock: Clock | None = None,
        **_: Any,
    ) -> int:
        """Persist each fact as its own knot and return the count stored.

        Args:
            facts: The sequence of fact strings to persist.
            store: The MemoryStore to write each fact into.
            clock: The run's time source; a ``FrozenClock`` under a deterministic
                run makes ``stored_at`` reproducible. Defaults to a
                :class:`SystemClock` — the wall clock is never read directly.

        Returns:
            The number of facts stored.

        Raises:
            TypeError: If store is not a MemoryStore or any fact is not a string.
            SubTapestryError: If any fact's write failed.
        """
        fact_list = list(facts)
        for fact in fact_list:
            if not isinstance(fact, str):
                raise TypeError(
                    f"SemanticFactWriter: every fact must be a string, got {type(fact).__name__}"
                )
        if not fact_list:
            return 0
        stored_at = (clock if clock is not None else SystemClock()).now().isoformat()
        with Tapestry() as inner:
            store_node = Parameter(
                "store", MemoryStore, default=store, _config=KnotConfig(id="store")
            )
            per_fact: dict[str, Knot] = {
                f"fact_{index}": StoredSemanticFact(
                    fact=fact,
                    store=store_node,
                    stored_at=stored_at,
                    _config=KnotConfig(id=f"fact_{index}"),
                )
                for index, fact in enumerate(fact_list)
            }
            Aggregator(
                combine=SemanticFactWriter._count_keys,
                _config=KnotConfig(id="written"),
                **per_fact,
            )
        run = await self._run_inner(inner)
        return run.outputs["written"]

    @staticmethod
    def _count_keys(**keys: str) -> int:
        """Count the keys the per-fact writes reported."""
        return len(keys)
