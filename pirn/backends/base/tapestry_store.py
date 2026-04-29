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
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    def all(self) -> list[Knot]:
        raise NotImplementedError(f"{type(self).__name__} must implement all()")

    def snapshot(self) -> TapestrySnapshot:
        raise NotImplementedError(f"{type(self).__name__} must implement snapshot()")
