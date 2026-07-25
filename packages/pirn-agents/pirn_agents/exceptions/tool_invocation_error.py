"""``ToolInvocationError`` — base of the tool-call error taxonomy."""

from __future__ import annotations


class ToolInvocationError(Exception):
    """Base class for every failure raised while invoking a tool.

    Carries a human-readable ``message`` and, optionally, the ``call_id``
    of the originating :class:`~pirn_agents.types.tool_call.ToolCall` so a
    failure can be correlated back to the call that produced it.

    Parameters
    ----------
    message:
        Human-readable description of the failure.
    call_id:
        Identifier of the originating tool call, or ``None`` when the
        failure is not tied to a specific call.
    """

    def __init__(self, message: str, call_id: str | None = None) -> None:
        self.message = message
        self.call_id = call_id
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        """Build the ``str`` form, appending the call id when present."""
        if self.call_id is None:
            return self.message
        return f"{self.message} (call_id={self.call_id})"
