from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Skipped(BaseModel):
    """A knot that was deliberately not run.

    Produced by Optional opt-out, non-selected Branch path, or closed Gate.
    Distinct from Err so downstream knots can treat skip-vs-fail differently.

    Attributes:
        reason: Why the knot did not run; recorded as the lineage row's
            ``skip_reason``.
        detail: Free-form context for the skip.
        propagates: Whether a knot skipped *because of* this one inherits
            ``reason`` instead of the engine's generic
            ``"parent_failed_or_skipped"``.  Set by a ``Gate`` closed by a
            ``Check`` that names its own ``skip_reason`` (an approval denial
            records ``"approval_denied"`` on every knot it stops, not only on
            the gate).  The engine sets it again on the inherited skip, so the
            reason carries through a chain of skipped knots.
    """

    model_config = ConfigDict(frozen=True)

    reason: str = "skipped"
    detail: dict[str, Any] = Field(default_factory=dict)
    propagates: bool = False

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return False

    @property
    def is_skipped(self) -> bool:
        return True

    def unwrap(self) -> object:  # pragma: no cover
        raise RuntimeError(f"unwrap() called on Skipped: {self.reason}")
