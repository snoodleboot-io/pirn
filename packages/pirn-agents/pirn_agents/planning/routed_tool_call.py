"""``RoutedToolCall`` — the ``Payload`` a plan-step routing hands back.

``RoutedToolCall`` is ``Payload[RoutedToolCallFrame, ToolCall]`` (PIR-874,
following PIR-868): ``data`` is the call the step was routed to — a
:class:`~pirn_agents.tools.tool_call.ToolCall` is a record that crosses a dozen
signatures and stays one — and ``metadata`` records the step, the tool chosen
and the tools it was chosen from. A bare call crossing the boundary between
:class:`~pirn_agents.planning.tool_router.ToolRouter` and
:class:`~pirn_agents.planning.tool_executor.ToolExecutor` said nothing about the
step that produced it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.planning.routed_tool_call_frame import RoutedToolCallFrame
from pirn_agents.tools.tool_call import ToolCall


class RoutedToolCall(Payload[RoutedToolCallFrame, ToolCall]):
    """A tool call together with the plan step it was routed from."""

    def __init__(self, call: ToolCall, *, step: str, candidates: Sequence[str]) -> None:
        frame = RoutedToolCallFrame(
            step=step, tool_name=call.tool_name, candidates=tuple(candidates)
        )
        super().__init__(metadata=frame, data=call)

    @staticmethod
    def _audit_form(value: PirnOpaqueValue) -> Any:
        """Audit a nested value through the ``PirnOpaqueValue`` contract it shares with this one."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["call"] = self._audit_form(self.data)
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
