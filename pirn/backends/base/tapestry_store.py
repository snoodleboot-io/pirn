from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.backends.base.tapestry_snapshot import TapestrySnapshot

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class TapestryStore:
    """Interface: where the tapestry's canonical definition lives.

    Implementations inherit from this class and override all methods.
    Use a Facade or Wrapper to integrate third-party stores.
    """

    def register(self, knot: Knot) -> None:
        """Add a knot.  Idempotent for the same instance; conflicts on id."""
        raise NotImplementedError(f"{type(self).__name__} must implement register()")

    def get(self, knot_id: str) -> Knot | None:
        """Retrieve a registered knot by its identifier.

        Args:
            knot_id: Stable string identifier assigned to the knot.

        Returns:
            The ``Knot`` instance, or ``None`` if not registered.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    def all(self) -> list[Knot]:
        """Return all currently registered knots.

        Returns:
            List of ``Knot`` instances in registration order.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement all()")

    def snapshot(self) -> TapestrySnapshot:
        """Capture an immutable view of the tapestry at this moment.

        The engine calls this before planning a run so that concurrent
        registrations during execution do not affect the in-flight plan.

        Returns:
            A frozen ``TapestrySnapshot`` containing the ordered list of
            registered knot ids.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement snapshot()")
