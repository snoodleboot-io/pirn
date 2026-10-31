"""``LatsNode`` — one node (a scored action trajectory) in the LATS search tree."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.lats.lats_node_frame import LatsNodeFrame


class LatsNode(AgentResult[LatsNodeFrame, tuple[str, ...]]):
    """A node in the LATS search tree.

    ``LatsNode`` is ``Payload[LatsNodeFrame, tuple[str, ...]]`` (PIR-874,
    following the PIR-868 pattern that :class:`LatsResult` already uses for the
    search's final answer): ``data`` is the ordered action trajectory from the
    root to this node, and ``metadata`` is the :class:`LatsNodeFrame` carrying
    the value model's estimate and the depth. A flat record crossing the knot
    boundary between :class:`ScoredLatsChild` and the loop that queues it
    carried the data and nothing else. The constructor takes the named fields
    (``trajectory``, ``value``, ``depth``); read them back as ``data`` and
    ``metadata.<field>``.
    """

    def __init__(self, trajectory: Sequence[str], value: float, depth: int) -> None:
        super().__init__(metadata=LatsNodeFrame(value=value, depth=depth), data=tuple(trajectory))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["trajectory"] = list(self.data)
        return audit
