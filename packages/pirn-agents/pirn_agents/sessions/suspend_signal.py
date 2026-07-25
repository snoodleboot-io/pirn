"""``SuspendSignal`` — emitted when an approval pause persists a run for HITL."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.resume_token import ResumeToken


@dataclass(frozen=True)
class SuspendSignal(PirnOpaqueValue):
    """The result of suspending a run at an approval gate.

    A suspend is not an error: it is a first-class value carrying the
    :class:`ResumeToken` a human uses to resume, plus a human-readable
    ``reason``. Its presence tells the caller the run is paused and persisted
    rather than completed.

    Attributes
    ----------
    token:
        The resumable handle for the persisted run.
    reason:
        Human-readable explanation of why the run paused.
    """

    token: ResumeToken
    reason: str = "awaiting human approval"

    def __post_init__(self) -> None:
        if not isinstance(self.token, ResumeToken):
            raise TypeError(
                f"SuspendSignal: token must be a ResumeToken, got {type(self.token).__name__}"
            )
        if not isinstance(self.reason, str) or not self.reason:
            raise TypeError("SuspendSignal: reason must be a non-empty str")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this signal."""
        return {"token": self.token.to_payload(), "reason": self.reason}

    @classmethod
    def from_payload(cls, payload: Any) -> SuspendSignal:
        """Reconstruct a signal from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"SuspendSignal.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            token=ResumeToken.from_payload(payload["token"]),
            reason=str(payload.get("reason", "awaiting human approval")),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
