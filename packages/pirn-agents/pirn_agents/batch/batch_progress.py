"""``BatchProgress`` — the resumable, checkpointable state of a batch run.

Records which item keys a batch has already completed so a killed run can resume
without re-doing finished work. It bridges to F14's durable-session machinery by
round-tripping through a :class:`~pirn_agents.sessions.run_state.RunState`: the
completed item keys are carried as the run's
:class:`~pirn_agents.sessions.execution_cursor.ExecutionCursor` completed steps,
so the exact same :class:`~pirn_agents.sessions.session_store.SessionStore` +
:class:`~pirn_agents.sessions.run_checkpoint.RunCheckpoint` content-addressing
that persists an agent run also persists a batch — no parallel store is invented.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.run_state import RunState


@dataclass(frozen=True)
class BatchProgress(PirnOpaqueValue):
    """The set of completed item keys for a batch, keyed by ``batch_id``.

    Attributes
    ----------
    batch_id:
        Stable id keying this batch's durable state (the session id under F14).
    completed_keys:
        The item keys already finished successfully. Frozen (immutable) so the
        value stays hashable and safe to share.
    total:
        Total item count when known (for reporting), else ``None``. Not carried
        through the F14 :class:`RunState` mapping — resume needs only the keys.
    """

    batch_id: str
    completed_keys: frozenset[str] = frozenset()
    total: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.batch_id, str) or not self.batch_id:
            raise TypeError("BatchProgress: batch_id must be a non-empty str")
        if not isinstance(self.completed_keys, frozenset):
            raise TypeError(
                f"BatchProgress: completed_keys must be a frozenset, "
                f"got {type(self.completed_keys).__name__}"
            )

    @property
    def completed_count(self) -> int:
        """How many items have completed."""
        return len(self.completed_keys)

    def is_complete(self, key: str) -> bool:
        """Whether ``key`` has already been completed."""
        return key in self.completed_keys

    def with_completed(self, key: str) -> BatchProgress:
        """Return a new progress with ``key`` recorded as completed."""
        return BatchProgress(
            batch_id=self.batch_id,
            completed_keys=self.completed_keys | {key},
            total=self.total,
        )

    def with_all(self, keys: Iterable[str]) -> BatchProgress:
        """Return a new progress with every key in ``keys`` recorded completed."""
        return BatchProgress(
            batch_id=self.batch_id,
            completed_keys=self.completed_keys | frozenset(keys),
            total=self.total,
        )

    def to_run_state(self) -> RunState:
        """Project the completed keys onto an F14 :class:`RunState` for persistence."""
        ordered = tuple(sorted(self.completed_keys))
        return RunState(
            session_id=self.batch_id,
            cursor=ExecutionCursor(step_index=len(ordered), completed_steps=ordered),
        )

    @classmethod
    def from_run_state(cls, state: RunState, *, total: int | None = None) -> BatchProgress:
        """Reconstruct progress from an F14 :class:`RunState`.

        Raises:
            TypeError: If ``state`` is not a RunState.
        """
        if not isinstance(state, RunState):
            raise TypeError(
                f"BatchProgress.from_run_state: state must be a RunState, "
                f"got {type(state).__name__}"
            )
        return cls(
            batch_id=state.session_id,
            completed_keys=frozenset(state.cursor.completed_steps),
            total=total,
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this progress."""
        return {
            "batch_id": self.batch_id,
            "completed_keys": sorted(self.completed_keys),
            "total": self.total,
        }

    @classmethod
    def from_payload(cls, payload: Any) -> BatchProgress:
        """Reconstruct progress from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"BatchProgress.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        raw_total = payload.get("total")
        return cls(
            batch_id=str(payload["batch_id"]),
            completed_keys=frozenset(str(k) for k in payload.get("completed_keys", ())),
            total=None if raw_total is None else int(raw_total),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
