"""``SpecialistInvocation`` — run one delegated specialist as a graph node.

A single-specialist knot: it invokes exactly one specialist (a
:class:`~pirn.nodes.sub_tapestry.SubTapestry`) through the engine entry point
(:meth:`SpecialistHandle.run`, i.e. the specialist's ``__call__`` — never its
``process()``; see PIR-769) and returns that specialist's answer normalised to
an :class:`AgentResponse`.

Wiring N of these as the parents of a single
:class:`~pirn.nodes.aggregator.Aggregator` lets the *engine* schedule the whole
fan-out concurrently (the scheduler starts every sibling as its own task the
moment it is ready; PIR-841) instead of the caller doing its own
``asyncio.gather`` over ``process()`` outside the engine. See PIR-714.

The specialist arrives as a
:class:`~pirn_agents.specializations.multi_agent.specialist_handle.SpecialistHandle`
— a non-``Knot`` opaque value — so it is an ordinary declared input rather than
a graph parent the engine would try to resolve, and nothing is held on the
instance.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.multi_agent.specialist_handle import SpecialistHandle
from pirn_agents.types.messaging.agent_response import AgentResponse


class SpecialistInvocation(Knot):
    """Invoke one specialist and surface its :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        specialist: SpecialistHandle,
        task: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(specialist=specialist, task=task, _config=_config, **kwargs)

    async def process(self, specialist: SpecialistHandle, task: str, **_: Any) -> AgentResponse:
        """Run ``specialist`` on ``task`` and return its normalised response.

        Args:
            specialist: The specialist to delegate to.
            task: The task string handed to the specialist (already framed by an
                upstream knot when the caller needs runtime framing).

        Returns:
            The specialist's :class:`AgentResponse`; a non-response result is
            wrapped in one with ``finish_reason="stop"``, exactly as the old
            fan-out sites normalised their gathered results.
        """
        raw = await specialist.run(task=task)
        if isinstance(raw, AgentResponse):
            return raw
        return AgentResponse(content=str(raw), finish_reason="stop")
