"""``ConsensusStrategy`` — interface for one consensus-reduction mechanism.

The OCP seam behind :class:`ConsensusAggregator`. Each concrete strategy owns a
single named consensus mechanism: it reports its selector name (:meth:`name`)
and builds the inner stage :class:`~pirn.core.knot.Knot` that performs the
reduction (:meth:`build`). The aggregator holds an ordered tuple of these
strategies and dispatches to the one whose name matches the requested strategy,
so adding a mechanism is a new subclass added to that tuple — no string branch
to edit.

Following the house interface style (never :class:`typing.Protocol`), this base
raises :class:`NotImplementedError` for :meth:`name` and :meth:`build`, while
:meth:`matches` is a concrete helper comparing the requested name to
:meth:`name`.
"""

from __future__ import annotations

from collections.abc import Mapping

from pirn.core.knot import Knot

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.types.messaging.agent_response import AgentResponse


class ConsensusStrategy:
    """Interface for one named consensus-reduction mechanism."""

    def name(self) -> str:
        """Return the selector name this strategy responds to."""
        raise NotImplementedError(f"{type(self).__name__} must implement name()")

    def matches(self, strategy: str) -> bool:
        """Return whether ``strategy`` selects this mechanism."""
        return strategy == self.name()

    def build(
        self,
        *,
        responses: Mapping[str, AgentResponse],
        llm: LLMProvider,
    ) -> Knot:
        """Build the inner stage knot that performs this reduction.

        Args:
            responses: The specialist responses to reduce.
            llm: The LLM provider (used only by LLM-mediated strategies).

        Returns:
            An unrun inner :class:`~pirn.core.knot.Knot` that produces the
            consensus :class:`AgentResponse`.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement build()")
