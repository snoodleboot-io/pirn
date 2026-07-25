"""A pending invocation of a :class:`Tool`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ToolCall(PirnOpaqueValue):
    """One tool invocation a planner has decided on.

    Attributes
    ----------
    tool_name:
        Identifier of the registered tool the agent intends to call.
    arguments:
        Mapping of argument name → value, conforming to the tool's
        ``input_schema``.
    call_id:
        Stable identifier the tool result will reference back.
    raw:
        Provider-native raw payload the call was decoded from (e.g. the
        original ``tool_use`` block). May be any object, including
        non-serialisable ones; audited via ``repr`` so content-addressing
        stays identity-stable. ``None`` when no raw form is retained.
    """

    tool_name: str
    arguments: Mapping[str, Any]
    call_id: str
    raw: Any | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "call_id": self.call_id,
            "raw": None if self.raw is None else repr(self.raw),
        }
