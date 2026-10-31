"""``ScoredLatsChild`` — score one candidate action and return it as a tree node.

One knot per candidate, so each value-model call has its own ``Result``, retry,
timeout and lineage row rather than being one turn of a Python loop inside
``afold`` that the run cannot see (Rule 11; PIR-874). The calls are independent
— a child's score depends on its own trajectory and nothing else — so the
engine may run them together.

Internal API. See ``lats_child_scorer.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.lats.lats_node import LatsNode
from pirn_agents.specializations.lats.trajectory_value_model import TrajectoryValueModel


class ScoredLatsChild(Knot):
    """Ask the value model what one candidate trajectory is worth."""

    def __init__(
        self,
        *,
        task: Knot | str,
        value_model: Knot | TrajectoryValueModel,
        trajectory: Knot | Sequence[str],
        depth: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            value_model=value_model,
            trajectory=trajectory,
            depth=depth,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        value_model: TrajectoryValueModel,
        trajectory: Sequence[str],
        depth: int,
        **_: Any,
    ) -> LatsNode:
        """Score ``trajectory`` and return the node it becomes.

        Args:
            task: The task being searched over.
            value_model: The scorer for candidate trajectories.
            trajectory: The child's full action sequence, parent actions included.
            depth: The child's depth, one below its parent's.

        Returns:
            The scored node, ready to be queued on the frontier.
        """
        actions = tuple(trajectory)
        value = await value_model.score(task, actions)
        return LatsNode(trajectory=actions, value=value, depth=depth)
