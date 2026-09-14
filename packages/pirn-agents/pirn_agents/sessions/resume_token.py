"""``ResumeToken`` — the resumable handle yielded when a run suspends for HITL."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ResumeToken(PirnOpaqueValue):
    """A durable handle that lets a suspended run be resumed later.

    ADR "agents speaks core" WS3 part 2 shape: the token binds the exact
    ``run_id`` a run suspended in (the engine already durably recorded it via
    ``RunHistory``/``DataStore`` — nothing else needs to persist it) to the
    content hash of the value that was pending approval when it suspended, so
    a resume can be verified against the run it actually names rather than an
    ad hoc session/checkpoint pairing. See
    :class:`~pirn_agents.sessions.approval_resumer.ApprovalResumer`.

    Attributes
    ----------
    run_id:
        The ``run_id`` of the run that suspended. Non-empty.
    output_hash:
        Content hash (``pirn.core.content_hasher.ContentHasher.hash``) of the value that
        was pending approval when the run suspended. Non-empty.
    """

    run_id: str
    output_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise TypeError("ResumeToken: run_id must be a non-empty str")
        if not isinstance(self.output_hash, str) or not self.output_hash:
            raise TypeError("ResumeToken: output_hash must be a non-empty str")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this token."""
        return {"run_id": self.run_id, "output_hash": self.output_hash}

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
            run_id=str(payload["run_id"]),
            output_hash=str(payload["output_hash"]),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
