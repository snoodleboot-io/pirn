"""``AgentRecursionError`` — base for agent-as-tool nesting guard failures."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class AgentRecursionError(PirnError, RuntimeError):
    """Base error for a rejected agent-as-tool nesting graph.

    Subclasses :class:`~pirn.exceptions.pirn_error.PirnError` in addition to
    ``RuntimeError`` so every existing ``except RuntimeError`` handler around
    a nested invocation keeps working unchanged, while new code can narrow to
    ``PirnError``.

    Raised by the recursion guard *before* an unsafe nested invocation runs, so
    a runaway or self-referential graph is stopped rather than exhausting the
    stack. Concrete subclasses distinguish a depth-cap breach
    (:class:`~pirn_agents.exceptions.agent_depth_exceeded_error.AgentDepthExceededError`)
    from a cycle
    (:class:`~pirn_agents.exceptions.agent_cycle_error.AgentCycleError`).
    """
