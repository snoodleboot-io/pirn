from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent

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
        event = StatusEvent(run_id=self._run_id, knot_id=knot_id, state=state, detail=detail)
        with self._lock:
            self._states[knot_id] = state
            self._events.append(event)
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(event)
            except Exception:
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
