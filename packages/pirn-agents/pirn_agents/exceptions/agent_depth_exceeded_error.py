"""``AgentDepthExceededError`` — the agent-as-tool nesting depth cap was hit."""

from __future__ import annotations

from pirn_agents.exceptions.agent_recursion_error import AgentRecursionError


class AgentDepthExceededError(AgentRecursionError):
    """Raised when nesting one more agent-as-tool would exceed ``max_depth``.

    Carries the ``depth`` that would have been entered and the configured
    ``max_depth`` cap for diagnostics. The guard raises this *before* the
    over-deep invocation runs, bounding fan-out cost.

    Attributes
    ----------
    depth:
        The nesting depth the rejected invocation would have occupied.
    max_depth:
        The configured maximum nesting depth.
    """

    def __init__(self, depth: int, max_depth: int) -> None:
        self.depth = depth
        self.max_depth = max_depth
        super().__init__(f"agent-as-tool nesting depth {depth} exceeds max_depth {max_depth}")
