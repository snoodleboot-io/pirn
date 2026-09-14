"""``FallbackResult`` — the typed outcome of a router + fallback-chain run."""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.routing.fallback_frame import FallbackFrame
from pirn_agents.tools.tool_result import ToolResult


class FallbackResult(AgentResult[FallbackFrame, ToolResult | None]):
    """Outcome of dispatching through a confidence-ordered fallback chain.

    ``FallbackResult`` is ``Payload[FallbackFrame, ToolResult | None]``
    (PIR-868, following the ADR agents-speaks-core WS6b pattern) — ``data``
    is the successful :class:`ToolResult` (or ``None`` on exhaustion), and
    ``metadata`` is the :class:`FallbackFrame` carrying the
    succeeded/chosen/attempted/skipped facts. Read ``succeeded``, ``chosen``,
    ``attempted`` and ``skipped`` as ``metadata.<field>`` and ``result`` as
    ``data``.
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

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["result"] = None if self.data is None else FallbackResult._audit_of(self.data)
        return audit

    @staticmethod
    def _audit_of(value: PirnOpaqueValue) -> Any:
        """Return ``value``'s audit form through the ``PirnOpaqueValue`` contract."""
        return value._pirn_audit_dict()
