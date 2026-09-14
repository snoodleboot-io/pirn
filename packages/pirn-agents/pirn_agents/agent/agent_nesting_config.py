"""``AgentNestingConfig`` — the default nesting cap for agent-as-tool calls.

Since the ADR "agents speaks core" (WS0/WS1) the depth and cycle guard for
nested runs is core's :class:`~pirn.core.run_nesting.RunNesting` frame,
enforced by ``Tapestry(max_nesting_depth=)`` and inherited (only ever
tightened) by inner runs.  What agents still decides is the *default* cap an
agent-as-tool call applies when its caller set none: this value is that
default, expressed as a root ``RunNesting`` frame whose ``max_depth`` is the
number of agent-as-tool frames that may be active at once (each such frame
is two nested runs — the call and the agent — which
:class:`~pirn_agents.tools.agent_tool_call.AgentToolCall` accounts for).

A frozen value rather than a module constant so a caller can hand a
*different* posture around as data — and so the limit is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.core.run_nesting import RunNesting


@dataclass(frozen=True)
class AgentNestingConfig(RunNesting, PirnOpaqueValue):
    """A root nesting frame carrying the agent-as-tool default cap.

    Attributes
    ----------
    max_depth:
        Maximum number of agent-as-tool frames that may be active at once. Must
        be >= 1. Defaults to 8, the chain's historical cap.
    """

    max_depth: int = 8

    def __post_init__(self) -> None:
        """Validate the recursion cap.

        Raises:
            ValueError: If ``max_depth`` is not an int >= 1.
        """
        if (
            isinstance(self.max_depth, bool)
            or not isinstance(self.max_depth, int)  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime-bound input; guard is deliberate
            or self.max_depth < 1
        ):
            raise ValueError(
                f"AgentNestingConfig: max_depth must be an int >= 1, got {self.max_depth!r}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"max_depth": self.max_depth}
