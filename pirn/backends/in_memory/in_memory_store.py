from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING

from pirn.backends.base.subscribable_store import SubscribableStore
from pirn.backends.base.tapestry_snapshot import TapestrySnapshot
from pirn.backends.base.tapestry_store import TapestryStore

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class InMemoryStore(TapestryStore, SubscribableStore):
    """In-memory TapestryStore.

    Implements SubscribableStore: callers can subscribe(callback) to receive
    each newly-registered Knot.  Used by the engine's mid-run extension mode.
    """

    def __init__(self) -> None:
        self._knots: dict[str, Knot] = {}
        self._lock = Lock()
        self._subscribers: dict[int, Callable[[Knot], None]] = {}
        self._next_token: int = 0

    def register(self, knot: Knot) -> None:
        with self._lock:
            existing = self._knots.get(knot.knot_id)
            if existing is not None and existing is not knot:
                raise ValueError(
                    f"knot id {knot.knot_id!r} already registered with a different instance"
                )
            is_new = existing is None
            self._knots[knot.knot_id] = knot
            subscribers = list(self._subscribers.values()) if is_new else []
        for cb in subscribers:
            try:
                cb(knot)
            except Exception:
                pass

    def get(self, knot_id: str) -> Knot | None:
        with self._lock:
            return self._knots.get(knot_id)

    def all(self) -> list[Knot]:
        with self._lock:
            return list(self._knots.values())

    def snapshot(self) -> TapestrySnapshot:
        with self._lock:
            return TapestrySnapshot(knot_ids=list(self._knots.keys()))

    def subscribe(self, callback: Callable[[Knot], None]) -> object:
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: object) -> None:
        with self._lock:
            self._subscribers.pop(token, None)  # type: ignore[arg-type]
