"""``ForkResult`` — metadata for a run forked from an F14 checkpoint."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.run_checkpoint import RunCheckpoint


@dataclass(frozen=True)
class ForkResult(PirnOpaqueValue):
    """The outcome of forking a run: the new checkpoint plus its provenance.

    The provenance fields make a forked run unambiguously distinguishable from the
    original: ``source_session_id`` / ``forked_from_checkpoint_id`` say what it
    branched from and ``fork_point`` says at which plan step, while
    ``new_session_id`` names the divergent branch.

    Attributes
    ----------
    new_session_id:
        Session id of the forked run.
    source_session_id:
        Session id the fork branched from.
    forked_from_checkpoint_id:
        Content id of the source checkpoint the fork was taken at.
    fork_point:
        Plan step index the fork diverges from (prior steps are preserved).
    checkpoint:
        The new :class:`RunCheckpoint` persisted for the forked run.
    """

    new_session_id: str
    source_session_id: str
    forked_from_checkpoint_id: str
    fork_point: int
    checkpoint: RunCheckpoint

    def __post_init__(self) -> None:
        if not isinstance(self.new_session_id, str) or not self.new_session_id:
            raise TypeError("ForkResult: new_session_id must be a non-empty str")
        if not isinstance(self.checkpoint, RunCheckpoint):
            raise TypeError(
                f"ForkResult: checkpoint must be a RunCheckpoint, "
                f"got {type(self.checkpoint).__name__}"
            )
        if isinstance(self.fork_point, bool) or not isinstance(self.fork_point, int):
            raise TypeError("ForkResult: fork_point must be an int")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of the fork provenance and checkpoint."""
        return {
            "new_session_id": self.new_session_id,
            "source_session_id": self.source_session_id,
            "forked_from_checkpoint_id": self.forked_from_checkpoint_id,
            "fork_point": self.fork_point,
            "checkpoint": self.checkpoint.to_payload(),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> ForkResult:
        """Reconstruct a fork result from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"ForkResult.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        return cls(
            new_session_id=str(payload["new_session_id"]),
            source_session_id=str(payload["source_session_id"]),
            forked_from_checkpoint_id=str(payload["forked_from_checkpoint_id"]),
            fork_point=int(payload["fork_point"]),
            checkpoint=RunCheckpoint.from_payload(payload["checkpoint"]),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
