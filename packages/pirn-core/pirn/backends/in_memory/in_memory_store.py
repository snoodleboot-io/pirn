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
        """Add a knot to the store and notify subscribers if it is new.

        Registering the same instance more than once is idempotent.
        Registering a *different* instance with a duplicate id raises.
        Subscribers are called outside the lock to avoid deadlocks.

        Args:
            knot: The knot to register.

        Raises:
            ValueError: If a different ``Knot`` instance with the same
                ``knot_id`` is already registered.
        """
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
        """Return the ``Knot`` for ``knot_id``, or ``None``.

        Args:
            knot_id: Identifier of the knot to retrieve.

        Returns:
            The registered ``Knot`` instance, or ``None`` if not found.
        """
        with self._lock:
            return self._knots.get(knot_id)

    def all(self) -> list[Knot]:
        """Return all registered knots.

        Returns:
            List of ``Knot`` instances in insertion order.
        """
        with self._lock:
            return list(self._knots.values())

    def snapshot(self) -> TapestrySnapshot:
        """Return a snapshot of currently registered knot ids.

        Returns:
            A frozen ``TapestrySnapshot``.
        """
        with self._lock:
            return TapestrySnapshot(knot_ids=list(self._knots.keys()))

    def subscribe(self, callback: Callable[[Knot], None]) -> object:
        """Register a callback invoked for each newly-registered knot.

        Args:
            callback: Callable that accepts a single ``Knot`` argument.

        Returns:
            An opaque integer token for use with :meth:`unsubscribe`.
        """
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: object) -> None:
        """Cancel a subscription.

        Args:
            token: The token returned by :meth:`subscribe`.  A token that
                has already been unsubscribed is silently ignored.
        """
        with self._lock:
            self._subscribers.pop(token, None)  # type: ignore[arg-type]
