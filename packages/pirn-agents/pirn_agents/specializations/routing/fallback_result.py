"""``FallbackResult`` — the typed outcome of a router + fallback-chain run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.routing.fallback_frame import FallbackFrame
from pirn_agents.tools.tool_result import ToolResult


class FallbackResult(AgentResult[FallbackFrame, ToolResult | None]):
    """Outcome of dispatching through a confidence-ordered fallback chain.

    ``FallbackResult`` is ``Payload[FallbackFrame, ToolResult | None]``
    (PIR-868, following the ADR agents-speaks-core WS6b pattern) — ``data``
    is the successful :class:`ToolResult` (or ``None`` on exhaustion), and
    ``metadata`` is the :class:`FallbackFrame` carrying the
    succeeded/chosen/attempted/skipped facts. The pre-ADR field names
    (``succeeded``, ``chosen``, ``result``, ``attempted``, ``skipped``) stay
    available as read-only properties, so every existing construction and
    attribute-access call site keeps compiling unchanged.
    """

    def __init__(
        self,
        succeeded: bool,
        chosen: str | None,
        result: ToolResult | None,
        attempted: tuple[str, ...],
        skipped: tuple[str, ...],
    ) -> None:
        frame = FallbackFrame(
            succeeded=succeeded, chosen=chosen, attempted=attempted, skipped=skipped
        )
        super().__init__(metadata=frame, data=result)

    @property
    def succeeded(self) -> bool:
        return self._metadata.succeeded

    @property
    def chosen(self) -> str | None:
        return self._metadata.chosen

    @property
    def result(self) -> ToolResult | None:
        return self._data

    @property
    def attempted(self) -> tuple[str, ...]:
        return self._metadata.attempted

    @property
    def skipped(self) -> tuple[str, ...]:
        return self._metadata.skipped

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(self._metadata._pirn_audit_dict())
        audit["result"] = None if self.result is None else self.result._pirn_audit_dict()
        return audit
