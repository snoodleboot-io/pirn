"""Subscription helpers for ``TapestryStore`` change notification.

Phase 3 mid-run extension: the engine, in opt-in ``extensible`` mode,
subscribes to the store for new-knot events and picks them up at the
end of each wave.

A store may opt into the protocol by implementing ``subscribe`` and
``unsubscribe``.  Stores that don't are still usable in non-extensible
mode (the default); attempting ``run(extensible=True)`` against a
non-subscribing store raises a clear error.

Why a separate protocol rather than baking it into ``TapestryStore``?
Backwards compatibility: Phase 2 stores (``InMemoryStore``,
``SQLiteStore``) don't implement subscribe.  Adding it as an optional
mixin keeps the base protocol minimal.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pirn.core.knot import Knot

# Type alias: a callback that receives the newly-registered Knot.
KnotSubscriber = Callable[["Knot"], None]


@runtime_checkable
class SubscribableStore(Protocol):
    """Optional capability protocol on top of ``TapestryStore``.

    Stores supporting mid-run extension implement ``subscribe`` (returns
    a token) and ``unsubscribe`` (called with the token).
    """

    def subscribe(self, callback: KnotSubscriber) -> object: ...

    def unsubscribe(self, token: object) -> None: ...
