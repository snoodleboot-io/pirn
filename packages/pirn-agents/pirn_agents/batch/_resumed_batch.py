"""``_ResumedBatch`` — sink for a batch every one of whose items already resumed.

``Aggregator`` requires at least one ``Knot`` parent, so a batch whose every
item has an ``Ok`` lineage row already (nothing left to run) has no parent to
give it. This tiny, parent-less knot carries the pre-computed
``BatchItemResult`` list straight through, so
:meth:`~pirn_agents.batch.map_agent.MapAgent.process`/``run`` can always
return *some* ``Knot`` as the batch's sink.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class _ResumedBatch(Knot):
    """Passes a precomputed, all-resumed result list through as this knot's output."""

    async def process(self, resumed: Any, **_: Any) -> Any:
        return resumed
