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
        """Register a callback to be called whenever a new knot is registered.

        The callback is invoked synchronously (or scheduled, depending on the
        implementation) with the newly-registered ``Knot`` instance.

        Args:
            callback: Callable that accepts a single ``Knot`` argument.

        Returns:
            An opaque subscription token.  Pass it to :meth:`unsubscribe`
            to cancel the subscription.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement subscribe()")

    def unsubscribe(self, token: object) -> None:
        """Cancel a subscription previously created by :meth:`subscribe`.

        Args:
            token: The opaque token returned by :meth:`subscribe`.  A token
                that has already been unsubscribed is silently ignored.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement unsubscribe()")
