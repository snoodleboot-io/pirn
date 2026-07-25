"""``TrajectoryStep`` — one recorded tool call in an agent trajectory."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class TrajectoryStep(PirnOpaqueValue):
    """A single step an agent took: the tool it chose, its args, and the result.

    Attributes
    ----------
    tool_name:
        Name of the tool the agent invoked at this step.
    arguments:
        The arguments passed to the tool (empty mapping when none).
    result:
        Optional recorded result of the call; not used by identity/choice
        metrics but retained so a trajectory is a faithful record.
    """

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    result: Any = None

    def __post_init__(self) -> None:
        """Validate the step's field types.

        Raises:
            TypeError: If ``tool_name`` is not a str or ``arguments`` is not a
                mapping.
        """
        if not isinstance(self.tool_name, str):
            raise TypeError(
                f"TrajectoryStep.tool_name must be a str, got {type(self.tool_name).__name__}"
            )
        if not isinstance(self.arguments, Mapping):
            raise TypeError(
                f"TrajectoryStep.arguments must be a mapping, got {type(self.arguments).__name__}"
            )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "result": repr(self.result),
        }
