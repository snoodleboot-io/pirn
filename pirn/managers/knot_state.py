from __future__ import annotations

from enum import StrEnum


class KnotState(StrEnum):
    """Lifecycle states a knot moves through during a run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
