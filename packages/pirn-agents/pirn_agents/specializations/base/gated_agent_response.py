"""``GatedAgentResponse`` — present a value as an AgentResponse, behind a gate.

Core :class:`~pirn.nodes.gate.gate.Gate` passes a **single** parent through, so
it cannot on its own feed a knot that takes several inputs. That is a problem
whenever a conditional step consumes both the gate's decision and some other
value — the common case being a check that must run only when an earlier
decision went a particular way.

This knot is the join. It takes the value and the gate's pass-through, so when
the gate is ``Skipped`` this knot is skipped, and everything downstream of it is
skipped too — the conditional work is never paid for.

Typical use, inside a loop iteration's tapestry::

    accepted = AcceptGate(verdict=verdict, threshold=t, _config=KnotConfig(id="gate"))
    keep_going = Gate(input=accepted, predicate=lambda ok: not ok,
                      _config=KnotConfig(id="continue"))
    response = GatedAgentResponse(content=candidate, gate=keep_going,
                                  _config=KnotConfig(id="candidate_response"))
    ReflectionCheck(response=response, llm=llm, _config=KnotConfig(id="reflect"))

Generalised from the PIR-713 pilot, where it existed inline as
``_CandidateResponse``; the shape is pattern-level, not evaluator-specific.

References:
    - :class:`pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class GatedAgentResponse(Knot):
    """Wrap ``content`` as an :class:`AgentResponse`, skipped when ``gate`` is."""

    def __init__(
        self,
        *,
        content: Knot | str,
        gate: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Join a value with a gate.

        Args:
            content: The text to present, or a :class:`Knot` producing it.
            gate: The gate whose pass-through decides whether this knot runs.
                Its value is not used — only its skip propagates.
            _config: Knot configuration carrying this knot's graph id.
            **kwargs: Forwarded to :class:`~pirn.core.knot.Knot`.
        """
        super().__init__(content=content, gate=gate, _config=_config, **kwargs)

    async def process(self, content: str, **_: Any) -> AgentResponse:
        """Present ``content`` as a response.

        Args:
            content: The resolved text.

        Returns:
            An :class:`AgentResponse` carrying ``content``.
        """
        return AgentResponse(content=content)
