"""``SessionIdentity`` — the stable identity + lifecycle stamp of a session.

This is the durable-session identity F14 owns and the plug point the F27 memory
seam consumes: the same :attr:`session_id` that keys a run's checkpoints and
threads can be passed to
:class:`~pirn_agents.memory_management.profile_key.ProfileKey` so a session's
lifecycle drives profile keying — without F14 importing F27 or F27 inventing
session machinery.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SessionIdentity(PirnOpaqueValue):
    """A durable session's stable id and creation time.

    Attributes
    ----------
    session_id:
        The stable, provider-neutral id keying all of a session's durable
        state (checkpoints, threads). Non-empty.
    created_at:
        Timezone-aware creation timestamp.
    """

    session_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise TypeError("SessionIdentity: session_id must be a non-empty str")
        if not isinstance(self.created_at, datetime):
            raise TypeError("SessionIdentity: created_at must be a datetime")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this identity."""
        return {"session_id": self.session_id, "created_at": self.created_at.isoformat()}

    @classmethod
    def from_payload(cls, payload: Any) -> SessionIdentity:
        """Reconstruct an identity from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"SessionIdentity.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            session_id=str(payload["session_id"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
