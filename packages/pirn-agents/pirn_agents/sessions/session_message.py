"""``SessionMessage`` — one role/content message captured in a run's state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SessionMessage(PirnOpaqueValue):
    """A single message in a run's message history.

    Attributes
    ----------
    role:
        The message author role (e.g. ``"user"``, ``"assistant"``,
        ``"system"``, ``"approval"``). Non-empty.
    content:
        The message text.
    """

    role: str
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, str) or not self.role:
            raise TypeError("SessionMessage: role must be a non-empty str")
        if not isinstance(self.content, str):
            raise TypeError(
                f"SessionMessage: content must be a str, got {type(self.content).__name__}"
            )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this message."""
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_payload(cls, payload: Any) -> SessionMessage:
        """Reconstruct a message from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"SessionMessage.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(role=str(payload["role"]), content=str(payload["content"]))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
