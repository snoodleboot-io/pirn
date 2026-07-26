"""Shared base abstractions for the specialization pattern family.

``AgentResult`` is the DIP/LSP base for the frozen ``*Result`` value objects;
``AgentPipeline`` is the base for the ``SubTapestry`` pattern knots. Both follow
the house NotImplementedError style (never :class:`typing.Protocol`).

Import each base from its concrete module
(``pirn_agents.specializations.base.agent_pipeline``, ``...agent_result``) —
this package does not re-export them.
"""

__all__: list[str] = []
