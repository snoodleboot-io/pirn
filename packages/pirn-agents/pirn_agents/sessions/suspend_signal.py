# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``SuspendSignal`` — the resumable handle read back from a suspended run."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.resume_token import ResumeToken

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


@dataclass(frozen=True)
class SuspendSignal(PirnOpaqueValue):
    """The result of suspending a run at an approval gate.

    A suspend is not an error: it is a first-class value carrying the
    :class:`ResumeToken` a human uses to resume, plus a human-readable
    ``reason``. Its presence tells the caller the run is paused rather than
    completed — the turn's own ``RunResult`` (already durably recorded) *is*
    the paused state; nothing else persists it.

    Attributes
    ----------
    token:
        The resumable handle for the suspended run.
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
    def from_run_result(cls, result: RunResult, *, knot_id: str) -> SuspendSignal | None:
        """Read a suspend signal back from a turn's ``RunResult``, if it suspended.

        Looks up ``knot_id``'s lineage row in ``result``. When that row's
        outcome is ``"skipped"`` (the shape
        :class:`~pirn_agents.sessions.suspending_approval_check.SuspendingApprovalCheck`
        produces), builds the :class:`ResumeToken` from the run's id and the
        content hash of the value that was pending approval (``knot_id``'s
        recorded ``response`` input).

        Args:
            result: The turn's ``RunResult``.
            knot_id: The id of the ``SuspendingApprovalCheck`` knot in that
                turn's graph.

        Returns:
            The ``SuspendSignal`` if ``knot_id`` suspended, else ``None`` —
            including when ``knot_id`` has no row at all (it did not run this
            turn) or completed normally (auto-approved).
        """
        row = next((r for r in result.lineage if r.knot_id == knot_id), None)
        if row is None or row.outcome != "skipped":
            return None
        pending_hash = row.parent_input_hashes.get("response", "")
        return cls(
            token=ResumeToken(run_id=result.run_id, output_hash=pending_hash),
            reason=row.skip_reason or "awaiting human approval",
        )

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
