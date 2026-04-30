from __future__ import annotations

import traceback
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

    @classmethod
    def for_knot(cls, knot_id: str, exc: BaseException) -> ExceptionRecord:
        """Build a placeholder record for an Err produced outside a run context.

        The engine re-registers it against the live ExceptionManager (which
        assigns a real run_id) when it collects the result.
        """
        return cls(
            run_id="<unbound>",
            knot_id=knot_id,
            exc_type=type(exc).__name__,
            message=str(exc),
            traceback_text="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
