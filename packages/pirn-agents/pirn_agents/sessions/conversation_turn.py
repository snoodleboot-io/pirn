"""``ConversationTurn`` — one indexed role/content turn in a durable thread."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ConversationTurn(PirnOpaqueValue):
    """A single turn in a multi-turn conversation thread.

    Attributes
    ----------
    index:
        Zero-based position of the turn in the thread. Non-negative.
    role:
        The turn author role (e.g. ``"user"``, ``"assistant"``). Non-empty.
    content:
        The turn text.
    """

    index: int
    role: str
    content: str

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise TypeError("ConversationTurn: index must be an int")
        if self.index < 0:
            raise ValueError(f"ConversationTurn: index must be >= 0, got {self.index}")
        if not isinstance(self.role, str) or not self.role:
            raise TypeError("ConversationTurn: role must be a non-empty str")
        if not isinstance(self.content, str):
            raise TypeError(
                f"ConversationTurn: content must be a str, got {type(self.content).__name__}"
            )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this turn."""
        return {"index": self.index, "role": self.role, "content": self.content}

    @classmethod
    def from_payload(cls, payload: Any) -> ConversationTurn:
        """Reconstruct a turn from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"ConversationTurn.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            index=int(payload["index"]),
            role=str(payload["role"]),
            content=str(payload["content"]),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
