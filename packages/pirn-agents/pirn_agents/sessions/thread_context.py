"""``ThreadContext`` — a resumed thread's turns as ordered F17 context items.

ADR agents-speaks-core WS6b: a value crossing a knot boundary is a
``Payload[Frame, Data]``. ``ThreadContextBuilder`` used to return a bare
``tuple[ContextItem, ...]``; PIR-874 (following PIR-868) wraps it at the
producer. ``ContextItem`` is a record shared by a dozen signatures and is
unchanged: it is the ``data``, while the frame
(:class:`~pirn_agents.sessions.thread_context_frame.ThreadContextFrame`) holds
the run-level facts (the thread's session id and the item count).

``sessions/`` must not import from ``specializations/``, so this subclasses
:class:`pirn.core.payload.Payload` directly and adds the same structural
``__eq__`` that ``AgentResult`` carries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.context_item import ContextItem
from pirn_agents.sessions.thread_context_frame import ThreadContextFrame


class ThreadContext(Payload[ThreadContextFrame, tuple[ContextItem, ...]]):
    """Ordered context items rebuilt from a durable conversation thread."""

    def __init__(self, items: Sequence[ContextItem], *, session_id: str) -> None:
        data = tuple(items)
        frame = ThreadContextFrame(session_id=session_id, item_count=len(data))
        super().__init__(metadata=frame, data=data)

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["items"] = self._audit_all(self.data)
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
