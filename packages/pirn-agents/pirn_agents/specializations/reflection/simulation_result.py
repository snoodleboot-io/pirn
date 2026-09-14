"""``SimulationResult`` — structured outcome record from :class:`OutcomeSimulator`."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.reflection.simulation_frame import SimulationFrame


class SimulationResult(AgentResult[SimulationFrame, str]):
    """Structured outcome simulation for a proposed action.

    ``SimulationResult`` is ``Payload[SimulationFrame, str]`` (PIR-868,
    following the ADR agents-speaks-core WS6b pattern) — ``data`` is the
    worst-case description (the scenario most likely to drive a caller's
    decision), and ``metadata`` is the :class:`SimulationFrame` carrying the
    best and neutral cases. The pre-ADR field names (``best_case``,
    ``neutral_case``, ``worst_case``) stay available as read-only
    properties, so every existing construction and attribute-access call
    site keeps compiling unchanged.
    """

    def __init__(self, best_case: str, neutral_case: str, worst_case: str) -> None:
        frame = SimulationFrame(best_case=best_case, neutral_case=neutral_case)
        super().__init__(metadata=frame, data=worst_case)

    @property
    def best_case(self) -> str:
        return self._metadata.best_case

    @property
    def neutral_case(self) -> str:
        return self._metadata.neutral_case

    @property
    def worst_case(self) -> str:
        return self._data

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["worst_case"] = self.worst_case
        return audit
