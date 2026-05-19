from __future__ import annotations


class IdentityResolver:
    """Base class for run identity resolution strategies.

    Implementations are attached to a ``Tapestry`` and called by the engine
    when ``RunRequest.actor`` is absent. Return ``None`` to indicate that this
    resolver cannot determine an identity — the engine will propagate ``None``
    without raising.
    """

    def resolve(self) -> str | None:
        """Return an actor string or None if identity cannot be determined."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement resolve()")
