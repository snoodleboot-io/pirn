"""``ToolCallBatch`` — the ordered tool calls a ReWOO plan hands to the executor.

PIR-868 rebased the specialization results on ``Payload[Frame, Data]`` and
PIR-874 applies the same rule (ADR agents-speaks-core WS6b: a value crossing a
knot boundary is a ``Payload``) to the ReWOO tool chain. The batch is a
*window* payload wrapping a tuple of :class:`ToolCall`: the frame
(:class:`ToolCallBatchFrame`) describes it, ``data`` is the calls. It subclasses
:class:`pirn.core.payload.Payload` directly because ``tools/`` must not import
from ``specializations/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_batch_frame import ToolCallBatchFrame


class ToolCallBatch(Payload[ToolCallBatchFrame, tuple[ToolCall, ...]]):
    """An ordered batch of :class:`ToolCall` plus its :class:`ToolCallBatchFrame`."""

    def __init__(self, calls: Sequence[ToolCall]) -> None:
        data = tuple(calls)
        frame = ToolCallBatchFrame(
            count=len(data), tool_names=tuple(call.tool_name for call in data)
        )
        super().__init__(metadata=frame, data=data)

    @staticmethod
    def _audit_form(value: PirnOpaqueValue) -> Any:
        """Audit a nested value through the ``PirnOpaqueValue`` contract it shares with this one."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["calls"] = [self._audit_form(call) for call in self.data]
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same type, equal frame and equal calls."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data

    def __repr__(self) -> str:
        return f"{type(self).__name__}(calls={self.data!r})"
