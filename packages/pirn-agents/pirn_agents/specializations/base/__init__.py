"""Shared base abstractions for the specialization pattern family.

``AgentResult`` is the DIP/LSP base for the frozen ``*Result`` value objects;
``AgentPipeline`` is the base for the ``SubTapestry`` pattern knots. Both follow
the house NotImplementedError style (never :class:`typing.Protocol`).
"""

from __future__ import annotations

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.agent_result import AgentResult

__all__ = ["AgentPipeline", "AgentResult"]
