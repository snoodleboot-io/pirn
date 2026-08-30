from __future__ import annotations

from typing import Any

from pirn.backends.base.value_retention import ValueRetention


class DataStore:
    """Interface: where intermediate values live, keyed by content hash.

    Lineage references values by hash; the data store holds them by hash.
    Scrubbing values from the data store does not affect lineage.

    Implementations inherit from this class and override all methods.
    """

    @property
    def retention(self) -> ValueRetention:
        """Declare how many values this backend keeps.

        Defaults to durable and unbounded, which is right for a real store.
        An ephemeral backend overrides this to declare its ceiling, so a
        caller that would otherwise grow the value plane without limit —
        ``LoopSubTapestry``, whose conversational flows produce a fresh set of
        values every turn — writes into a bounded working set instead.

        This exists so the engine never has to ask what *class* a store is,
        mirroring :attr:`pirn.backends.base.run_history.RunHistory.retention`
        on the lineage plane.  See PIR-839.
        """
        return ValueRetention()

    async def put(self, content_hash: str, value: Any) -> None:
        """Persist a value under its content hash.

        Args:
            content_hash: SHA-256 hex digest (with or without ``sha256:`` prefix)
                that uniquely identifies the serialized value.
            value: Arbitrary Python object to store.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement put()")

    async def get(self, content_hash: str) -> Any:
        """Retrieve a value by its content hash.

        Args:
            content_hash: Hash previously passed to :meth:`put`.

        Returns:
            The stored value.

        Raises:
            KeyError: If no value is stored under ``content_hash``.  A bounded
                backend that dropped the value under its own ceiling raises
                :class:`pirn.exceptions.value_evicted_error.ValueEvictedError`,
                a ``KeyError`` subclass, so the caller can tell "this store
                let it go" from "this was never here".  A read that cannot be
                satisfied always raises; it never returns ``None`` or a
                default that could be mistaken for a stored value.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement get()")

    async def has(self, content_hash: str) -> bool:
        """Return ``True`` if a value is stored under ``content_hash``.

        Args:
            content_hash: Hash to check.

        Returns:
            ``True`` if present, ``False`` otherwise.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement has()")

    async def scrub(self, content_hash: str) -> None:
        """Remove a value.  Lineage referencing it remains intact."""
        raise NotImplementedError(f"{type(self).__name__} must implement scrub()")
