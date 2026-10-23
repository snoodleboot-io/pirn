"""``ToolCallBatchFrame`` — lineage metadata for a batch of planned tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ToolCallBatchFrame(PirnOpaqueValue):
    """Frame half of ``Payload[ToolCallBatchFrame, tuple[ToolCall, ...]]`` (PIR-874).

    Describes the batch without carrying the calls themselves, which are the
    payload's ``data`` (ADR agents-speaks-core WS6b).

    Attributes
    ----------
    count:
        Number of calls in the batch.
    tool_names:
        The tool name of each call, in batch order.
    """

    count: int
    tool_names: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"count": self.count, "tool_names": list(self.tool_names)}
