"""``LatsChildScorer`` — score every action the proposer returned, as N knots.

The candidates are not known until the proposer has run, so the fan-out over
them cannot be declared when the iteration's tapestry is built. This knot sits
downstream of the proposer in that tapestry and opens an inner run with one
:class:`~pirn_agents.specializations.lats.scored_lats_child.ScoredLatsChild` per
action (Rule 11; PIR-874) — the shape that lets the round's N value-model calls
each have a lineage row, and lets the engine schedule them instead of a ``for``
loop in ``afold``.

Internal API. See ``lats_step_loop.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.specializations.lats.lats_node import LatsNode
from pirn_agents.specializations.lats.scored_lats_child import ScoredLatsChild
from pirn_agents.specializations.lats.trajectory_value_model import TrajectoryValueModel


class LatsChildScorer(NestedRunKnot):
    """Turn one node's proposed actions into scored children."""

    #: Inner-run knot ids (Rule: no module-level constants).
    _child_prefix: ClassVar[str] = "child_"
    _children_id: ClassVar[str] = "children"

    def __init__(
        self,
        *,
        task: Knot | str,
        value_model: Knot | TrajectoryValueModel,
        actions: Knot | Sequence[str],
        trajectory: Knot | Sequence[str],
        depth: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            value_model=value_model,
            actions=actions,
            trajectory=trajectory,
            depth=depth,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        value_model: TrajectoryValueModel,
        actions: Sequence[str],
        trajectory: Sequence[str],
        depth: int,
        **_: Any,
    ) -> tuple[LatsNode, ...]:
        """Score each action as a child of ``trajectory``.

        Args:
            task: The task being searched over.
            value_model: The scorer for candidate trajectories.
            actions: The proposer's candidate next actions.
            trajectory: The expanded node's action sequence.
            depth: The expanded node's depth.

        Returns:
            One scored :class:`LatsNode` per action, in the order proposed.
        """
        action_list = list(actions)
        if not action_list:
            return ()
        parent = tuple(trajectory)
        with Tapestry() as inner:
            model_node = Parameter(
                "value_model",
                TrajectoryValueModel,
                default=value_model,
                _config=KnotConfig(id="value_model"),
            )
            per_action: dict[str, Knot] = {
                f"{type(self)._child_prefix}{index}": ScoredLatsChild(
                    task=task,
                    value_model=model_node,
                    trajectory=(*parent, action),
                    depth=depth + 1,
                    _config=KnotConfig(id=f"{type(self)._child_prefix}{index}"),
                )
                for index, action in enumerate(action_list)
            }
            Aggregator(
                combine=LatsChildScorer._in_proposed_order,
                _config=KnotConfig(id=type(self)._children_id),
                **per_action,
            )
        run = await self._run_inner(inner)
        return run.outputs[type(self)._children_id]

    @staticmethod
    def _in_proposed_order(**children: LatsNode) -> tuple[LatsNode, ...]:
        """Put the scored children back in the order the proposer named them.

        The frontier is a heap keyed on ``(-value, sequence, node)``, so the
        sequence numbers ``afold`` hands out break ties — and ties would be
        broken by scheduling order rather than by the proposer's if this sorted
        on the mapping's order instead of the index.
        """
        ordered = sorted(children.items(), key=lambda item: int(item[0].removeprefix("child_")))
        return tuple(child for _key, child in ordered)
