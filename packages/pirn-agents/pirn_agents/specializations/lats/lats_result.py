"""``LatsResult`` — the typed outcome of a budgeted LATS search."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.lats.lats_frame import LatsFrame


class LatsResult(AgentResult[LatsFrame, tuple[str, ...]]):
    """Outcome of a budget-bounded LATS search.

    ``LatsResult`` is ``Payload[LatsFrame, tuple[str, ...]]`` (PIR-868,
    following the ADR agents-speaks-core WS6b pattern) — ``data`` is the
    highest-value action trajectory found within budget, and ``metadata``
    is the :class:`LatsFrame` carrying the value/nodes-expanded/budget
    facts. The constructor takes the pattern's named fields (``best_trajectory``,
    ``best_value``, ``nodes_expanded``, ``budget_exhausted``), and each is also a read-only
    property.
    """

    def __init__(
        self,
        best_trajectory: tuple[str, ...],
        best_value: float,
        nodes_expanded: int,
        budget_exhausted: bool,
    ) -> None:
        frame = LatsFrame(
            best_value=best_value,
            nodes_expanded=nodes_expanded,
            budget_exhausted=budget_exhausted,
        )
        super().__init__(metadata=frame, data=tuple(best_trajectory))

    @property
    def best_trajectory(self) -> tuple[str, ...]:
        return self._data

    @property
    def best_value(self) -> float:
        return self._metadata.best_value

    @property
    def nodes_expanded(self) -> int:
        return self._metadata.nodes_expanded

    @property
    def budget_exhausted(self) -> bool:
        return self._metadata.budget_exhausted

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["best_trajectory"] = list(self.best_trajectory)
        return audit
