"""``ThreadContextFrame`` — run-level facts of a rebuilt thread context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ThreadContextFrame(PirnOpaqueValue):
    """Which thread a context was rebuilt from, and how many items it holds.

    The frame half of the ``Payload[ThreadContextFrame, tuple[ContextItem, ...]]``
    split (PIR-868, PIR-874).

    Attributes
    ----------
    session_id:
        The ``ConversationThread.session_id`` the items were read from.
    item_count:
        How many context items were produced (one per turn).
    """

    session_id: str
    item_count: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"session_id": self.session_id, "item_count": self.item_count}
