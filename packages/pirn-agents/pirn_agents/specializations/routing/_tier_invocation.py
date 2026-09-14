"""``_TierInvocation`` — call one cascade tier's provider callable as a graph node.

Internal knot for
:class:`~pirn_agents.specializations.routing._attempt_tier._AttemptTier`
(PIR-867): ``tier.invoke`` is the cascade's own provider seam — a bare async
callable, not a :class:`~pirn_agents.tools.tool.Tool` — so this is *not* a
``ToolInvocation``; it exists so the call runs through the engine like any
other node, with its own ``Result`` and lineage row, instead of being
awaited inline inside ``_AttemptTier.process()``.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.routing.cascade_tier import CascadeTier


class _TierInvocation(Knot):
    """Call ``tier.invoke(request)`` and return its raw output."""

    def __init__(
        self,
        *,
        tier: Knot | CascadeTier,
        request: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tier=tier, request=request, _config=_config, **kwargs)

    async def process(self, tier: CascadeTier, request: Any, **_: Any) -> Any:
        """Call this tier's provider and return its output."""
        return await tier.invoke(request)
