"""``_ReviewerInvocation`` — run one reviewer as a graph node.

Sibling of :class:`~pirn_agents.specializations.multi_agent.specialist_invocation.SpecialistInvocation`
for the round-robin review shape: a reviewer is invoked with ``response=``
(the running draft) rather than ``task=``, through the engine entry point
(:meth:`_SpecialistInvoker.invoke_specialist`, i.e. the reviewer's
``__call__`` — never its ``process()``; see PIR-769) so each review round is a
real knot with its own ``Result``, history record, and lineage instead of a
step inside a hand-rolled Python ``for`` loop.

Preserves the original ``RoundRobinReview`` semantics exactly: a reviewer
whose result is not an :class:`AgentResponse` leaves the running draft
unchanged (rather than being coerced to one, which is what
``SpecialistInvocation`` does for the task-invocation shape — this class is
deliberately not that one, because that coercion would change behaviour here).

The reviewer is held on a ``_mutable_`` slot rather than passed to
``super().__init__``, mirroring ``SpecialistInvocation``: it is opaque data
this knot invokes itself, not an upstream value for the engine to resolve.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.multi_agent._specialist_invoker import (
    _SpecialistInvoker,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


class _ReviewerInvocation(Knot):
    """Invoke one reviewer on the running draft and surface the revised response."""

    def __init__(
        self,
        *,
        reviewer: SubTapestry,
        response: Knot | AgentResponse,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, _config=_config, **kwargs)
        # Held as _mutable_ data, NOT passed to super(): see
        # SpecialistInvocation's module docstring for why a Knot-typed
        # opaque callee cannot be wired as a normal parent.
        object.__setattr__(self, "_mutable_reviewer", reviewer)

    async def process(self, response: AgentResponse, **_: Any) -> AgentResponse:
        """Run the held reviewer on ``response`` and return the revised draft.

        Args:
            response: The running draft before this reviewer sees it.

        Returns:
            The reviewer's :class:`AgentResponse` when it produced one;
            otherwise ``response`` unchanged, exactly as the original
            hand-rolled loop silently kept the prior draft.
        """
        raw = await _SpecialistInvoker.invoke_specialist(self._mutable_reviewer, response=response)
        if isinstance(raw, AgentResponse):
            return raw
        return response
