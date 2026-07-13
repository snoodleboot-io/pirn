"""``ResumeToken`` — the resumable handle yielded when a run suspends for HITL."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ResumeToken(PirnOpaqueValue):
    """A durable handle that lets a suspended run be resumed later.

    The token binds a ``session_id`` to the exact ``checkpoint_id`` persisted at
    suspend time, so resume can verify it is continuing the state it paused on.

    Attributes
    ----------
    session_id:
        The suspended run's session id. Non-empty.
    checkpoint_id:
        Content-addressed id of the persisted checkpoint. Non-empty.
    """

    session_id: str
    checkpoint_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise TypeError("ResumeToken: session_id must be a non-empty str")
        if not isinstance(self.checkpoint_id, str) or not self.checkpoint_id:
            raise TypeError("ResumeToken: checkpoint_id must be a non-empty str")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this token."""
        return {"session_id": self.session_id, "checkpoint_id": self.checkpoint_id}

    @classmethod
    def from_payload(cls, payload: Any) -> ResumeToken:
        """Reconstruct a token from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"ResumeToken.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        return cls(
            session_id=str(payload["session_id"]),
            checkpoint_id=str(payload["checkpoint_id"]),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
