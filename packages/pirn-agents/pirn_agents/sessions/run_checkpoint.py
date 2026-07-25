"""``RunCheckpoint` — a content-addressed, serialisable checkpoint of a run."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.run_state import RunState


@dataclass(frozen=True)
class RunCheckpoint(PirnOpaqueValue):
    """A :class:`RunState` tagged with a content-addressed id.

    ``checkpoint_id`` is a SHA-256 over the canonical JSON of the state, so two
    checkpoints of identical state share an id (enabling dedup) and any change
    to messages, plan, tool results, or cursor yields a different id.

    Attributes
    ----------
    checkpoint_id:
        Hex SHA-256 digest of the canonical state payload.
    state:
        The captured :class:`RunState`.
    """

    checkpoint_id: str
    state: RunState

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint_id, str) or not self.checkpoint_id:
            raise TypeError("RunCheckpoint: checkpoint_id must be a non-empty str")
        if not isinstance(self.state, RunState):
            raise TypeError(
                f"RunCheckpoint: state must be a RunState, got {type(self.state).__name__}"
            )

    @staticmethod
    def content_hash(state: RunState) -> str:
        """Return the SHA-256 hex digest of ``state``'s canonical JSON payload."""
        canonical = json.dumps(state.to_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def create(cls, state: RunState) -> RunCheckpoint:
        """Build a checkpoint whose id is the content hash of ``state``.

        Raises:
            TypeError: If ``state`` is not a RunState.
        """
        if not isinstance(state, RunState):
            raise TypeError(
                f"RunCheckpoint.create: state must be a RunState, got {type(state).__name__}"
            )
        return cls(checkpoint_id=cls.content_hash(state), state=state)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this checkpoint."""
        return {"checkpoint_id": self.checkpoint_id, "state": self.state.to_payload()}

    @classmethod
    def from_payload(cls, payload: Any) -> RunCheckpoint:
        """Reconstruct a checkpoint from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"RunCheckpoint.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            checkpoint_id=str(payload["checkpoint_id"]),
            state=RunState.from_payload(payload["state"]),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"checkpoint_id": self.checkpoint_id, "state": self.state._pirn_audit_dict()}
