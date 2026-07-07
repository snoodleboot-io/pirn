"""``ToolArgumentValidationError`` — a call's arguments failed validation."""

from __future__ import annotations

from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError


class ToolArgumentValidationError(ToolInvocationError):
    """Raised when a :class:`ToolCall`'s arguments fail schema validation.

    Carries a machine-readable ``detail`` mapping (e.g. offending argument
    name to the reason it was rejected) alongside the human-readable
    message so callers can react programmatically.

    Parameters
    ----------
    tool_name:
        Name of the tool whose arguments were rejected.
    detail:
        Machine-readable mapping of argument name to failure reason.
    call_id:
        Identifier of the originating tool call, or ``None``.
    """

    def __init__(
        self,
        tool_name: str,
        detail: dict[str, str],
        call_id: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.detail = detail
        super().__init__(
            f"Invalid arguments for tool '{tool_name}': {detail}", call_id
        )
