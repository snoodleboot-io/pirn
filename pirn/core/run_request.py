from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunRequest(BaseModel):
    """Input to a tapestry run.

    Carries parameter bindings and a run id.  Triggers build these from
    external events; callers build them directly for one-off runs.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex}")
    parameters: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
