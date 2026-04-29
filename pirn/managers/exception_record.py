from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ExceptionRecord(BaseModel):
    """A captured exception, detached from frames, safe to serialise."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(
        default_factory=lambda: f"exc-{uuid.uuid4().hex}",
        description="Run-scoped identifier; lineage records refer to this.",
    )
    run_id: str
    knot_id: str
    exc_type: str
    message: str
    traceback_text: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
