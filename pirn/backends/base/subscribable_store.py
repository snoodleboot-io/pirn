from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.knot import Knot

KnotSubscriber = Callable[["Knot"], None]


class SubscribableStore:
    """Interface: optional capability for TapestryStore implementations that
    support mid-run knot registration callbacks.

    Stores supporting mid-run extension inherit from both TapestryStore and
    SubscribableStore and implement subscribe/unsubscribe.

    The engine checks for this capability before enabling extensible mode.
    """

    def subscribe(self, callback: KnotSubscriber) -> object:
        raise NotImplementedError(f"{type(self).__name__} must implement subscribe()")

    def unsubscribe(self, token: object) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement unsubscribe()")
