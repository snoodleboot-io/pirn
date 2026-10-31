"""``ValidatedToolCall`` — the ``Payload`` a passed tool-call validation hands back.

``ValidatedToolCall`` is ``AgentResult[ValidatedToolCallFrame, ToolCall]``
(PIR-874, following PIR-868): ``data`` is the call, unchanged — a
:class:`~pirn_agents.tools.tool_call.ToolCall` is a record that crosses a dozen
signatures and stays one — and ``metadata`` says what it was validated against.
The validator used to hand the bare call back, which told the next knot nothing
about the check it had passed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.tool_use.validated_tool_call_frame import (
    ValidatedToolCallFrame,
)
from pirn_agents.tools.tool_call import ToolCall


class ValidatedToolCall(AgentResult[ValidatedToolCallFrame, ToolCall]):
    """A tool call that passed validation, with the declaration it passed against."""

    def __init__(self, call: ToolCall, declared_tools: Sequence[str]) -> None:
        frame = ValidatedToolCallFrame(
            tool_name=call.tool_name, declared_tools=tuple(declared_tools)
        )
        super().__init__(metadata=frame, data=call)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["call"] = self._audit_form(self.data)
        return audit
