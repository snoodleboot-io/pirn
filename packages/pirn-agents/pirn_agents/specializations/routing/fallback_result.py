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
    succeeded/chosen/attempted/skipped facts. ``succeeded``, ``chosen``,
    ``attempted`` and ``skipped`` read the frame and ``result`` reads the data,
    as read-only properties.
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
        audit = dict(super()._pirn_audit_dict())
        audit["result"] = None if self.result is None else FallbackResult._audit_of(self.result)
        return audit

    @staticmethod
    def _audit_of(value: PirnOpaqueValue) -> Any:
        """Return ``value``'s audit form through the ``PirnOpaqueValue`` contract."""
        return value._pirn_audit_dict()
