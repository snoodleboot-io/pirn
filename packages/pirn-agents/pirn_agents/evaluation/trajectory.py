"""``Trajectory`` — an ordered record of the steps an agent took."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.trajectory_step import TrajectoryStep


@dataclass(frozen=True)
class Trajectory(PirnOpaqueValue):
    """An ordered sequence of :class:`TrajectoryStep`\\ s from one agent run.

    The unit the trajectory-quality metrics consume: a recorded (``actual``)
    trajectory is scored against an expected/gold one for tool-choice accuracy
    and step efficiency, or on its own for redundant-call rate.

    Attributes
    ----------
    steps:
        The steps taken, in execution order.
    """

    steps: tuple[TrajectoryStep, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalise ``steps`` to a ``tuple[TrajectoryStep, ...]``.

        Raises:
            TypeError: If ``steps`` is not a sequence, or any element is not a
                :class:`TrajectoryStep`.
        """
        if isinstance(self.steps, (str, bytes)) or not isinstance(self.steps, Sequence):
            raise TypeError(
                f"Trajectory.steps must be a sequence of TrajectoryStep, "
                f"got {type(self.steps).__name__}"
            )
        steps = tuple(self.steps)
        for index, step in enumerate(steps):
            if not isinstance(step, TrajectoryStep):
                raise TypeError(
                    f"Trajectory.steps[{index}] must be a TrajectoryStep, got {type(step).__name__}"
                )
        object.__setattr__(self, "steps", steps)

    @property
    def tool_names(self) -> tuple[str, ...]:
        """The tool name of each step, in order."""
        return tuple(step.tool_name for step in self.steps)

    def __len__(self) -> int:
        return len(self.steps)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"steps": [step._pirn_audit_dict() for step in self.steps]}
