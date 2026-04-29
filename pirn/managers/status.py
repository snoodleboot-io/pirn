"""Observable per-knot run state.

The single source of truth for "what is happening in this run."  Every
state transition emits a ``StatusEvent``; subscribers receive events as
they happen.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field


class KnotState(StrEnum):
    """Lifecycle states a knot moves through during a run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class StatusEvent(BaseModel):
    """A single state transition for a knot in a run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    knot_id: str
    state: KnotState
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detail: str | None = None


Subscriber = Callable[[StatusEvent], None]


class StatusManager:
    """Tracks per-knot state and broadcasts transitions to subscribers."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._states: dict[str, KnotState] = {}
        self._events: list[StatusEvent] = []
        self._subscribers: list[Subscriber] = []
        self._lock = Lock()

    def transition(
        self,
        knot_id: str,
        state: KnotState,
        detail: str | None = None,
    ) -> StatusEvent:
        """Record a state transition and broadcast it.

        Subscribers run after the lock is released so a slow subscriber
        cannot block other transitions.
        """
        event = StatusEvent(
            run_id=self._run_id, knot_id=knot_id, state=state, detail=detail
        )
        with self._lock:
            self._states[knot_id] = state
            self._events.append(event)
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(event)
            except Exception:
                # Subscribers must not break the run.  Phase 3 routes this
                # through structured logging.
                pass
        return event

    def subscribe(self, subscriber: Subscriber) -> None:
        with self._lock:
            self._subscribers.append(subscriber)

    def get(self, knot_id: str) -> KnotState:
        with self._lock:
            return self._states.get(knot_id, KnotState.PENDING)

    def snapshot(self) -> dict[str, KnotState]:
        with self._lock:
            return dict(self._states)

    def events(self) -> list[StatusEvent]:
        with self._lock:
            return list(self._events)
