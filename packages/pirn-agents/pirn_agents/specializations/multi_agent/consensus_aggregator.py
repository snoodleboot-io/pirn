"""``ConsensusAggregator`` — deprecated; construct :class:`ConsensusPipeline` directly.

Renamed (ADR agents-speaks-core WS5b): this class claimed core's
:class:`~pirn.nodes.aggregator.Aggregator` in its name without being one —
``responses`` arrives as a single already-assembled mapping and ``process()``
*selects* which of two named strategies builds the inner reduction, an OCP
dispatch shape, not a fan-in. See
:class:`~pirn_agents.specializations.multi_agent.consensus_pipeline.ConsensusPipeline`
for the implementation and full docstring; this name is kept importable for
one deprecation cycle and raises a ``DeprecationWarning`` on construction via
``Knot._deprecated_since`` (``pirn_agents.builder.agent_pattern_registry``'s
``"consensus"`` pattern now resolves to ``ConsensusPipeline`` directly).

ADR: agents-speaks-core WS5a, WS5b.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.multi_agent.consensus_pipeline import ConsensusPipeline
from pirn_agents.types.messaging.agent_response import AgentResponse


class ConsensusAggregator(ConsensusPipeline):
    """Deprecated: construct :class:`ConsensusPipeline` directly."""

    _deprecated_since: ClassVar[str | None] = "agents-speaks-core WS5b"

    def __init__(
        self,
        *,
        responses: Knot | Mapping[str, AgentResponse],
        llm: Knot | LLMProvider,
        strategy: Knot | str = "llm_synthesis",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(responses=responses, llm=llm, strategy=strategy, _config=_config, **kwargs)
