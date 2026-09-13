from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from threading import Lock
from typing import Any

from pirn.managers.knot_state import KnotState
from pirn.managers.status_event import StatusEvent

Subscriber = Callable[[StatusEvent], None]

_logger = logging.getLogger(__name__)


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
        extra: Mapping[str, Any] | None = None,
    ) -> StatusEvent:
        """Record a state transition and broadcast it.

        Subscribers run after the lock is released so a slow subscriber
        cannot block other transitions.

        Args:
            knot_id: The knot whose state changed.
            state: The new lifecycle state.
            detail: Optional short human-readable summary.
            extra: Optional structured metadata (e.g. span-like fields a
                downstream domain wants on the event); defaults to an empty
                mapping so existing callers see no change.
        """
        event = StatusEvent(
            run_id=self._run_id,
            knot_id=knot_id,
            state=state,
            detail=detail,
            extra=dict(extra) if extra is not None else {},
        )
        with self._lock:
            self._states[knot_id] = state
            self._events.append(event)
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub(event)
            except Exception:
                _logger.warning(
                    "StatusManager: subscriber raised for knot %r transition to %r",
                    knot_id,
                    state,
                    exc_info=True,
                )
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
