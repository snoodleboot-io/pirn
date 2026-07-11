"""``AgentCycleError`` — an agent-as-tool graph transitively calls itself."""

from __future__ import annotations

from pirn_agents.exceptions.agent_recursion_error import AgentRecursionError


class AgentCycleError(AgentRecursionError):
    """Raised when an agent would re-enter one already active on the call stack.

    Detected before the re-entrant invocation runs, so a self-referential graph
    (``A`` → ``B`` → ``A``) is rejected instead of recursing forever. Carries
    the offending agent ``key`` and the active ``stack`` at detection time.

    Attributes
    ----------
    key:
        Stable identity of the agent that would have been re-entered.
    stack:
        The agent keys already active, outermost first.
    """

    def __init__(self, key: str, stack: tuple[str, ...]) -> None:
        self.key = key
        self.stack = stack
        super().__init__(
            f"agent-as-tool cycle detected: {key!r} is already active in {list(stack)}"
        )
