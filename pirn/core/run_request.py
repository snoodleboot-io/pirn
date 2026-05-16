from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunRequest(BaseModel):
    """Input descriptor for a single tapestry run.

    ``RunRequest`` carries everything the scheduler needs to start a run:
    a unique run id, parameter bindings, and the submission timestamp.
    Trigger implementations build ``RunRequest`` instances from external
    events (webhooks, queue messages, schedules); callers constructing
    one-off runs can instantiate it directly with only ``parameters``.

    All fields have defaults so ``RunRequest()`` is valid for a parameter-
    free pipeline; only set the fields you need to override.

    Attributes:
        run_id: Unique identifier for this run.  Defaults to a UUID-based
            string of the form ``'run-<hex>'``.  Override when you need
            deterministic ids for testing or idempotency checks.
        parameters: Mapping of ``Parameter.name`` → caller-supplied value.
            Values are validated against each ``Parameter``'s declared type
            before the scheduler dispatches any knots.
        submitted_at: UTC wall-clock time when this request was created.
            Defaults to the current time at construction.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex}")
    parameters: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
