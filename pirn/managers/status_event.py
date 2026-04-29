from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from pirn.managers.knot_state import KnotState


class StatusEvent(BaseModel):
    """A single state transition for a knot in a run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    knot_id: str
    state: KnotState
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detail: str | None = None
