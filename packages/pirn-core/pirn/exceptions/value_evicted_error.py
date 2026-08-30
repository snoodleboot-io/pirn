"""Raised when a ``DataStore`` is asked for a value it evicted under its ceiling."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class ValueEvictedError(PirnError, KeyError):
    """The value was in this store and the store dropped it to stay bounded.

    A bounded ``DataStore`` — one whose
    :attr:`~pirn.backends.base.data_store.DataStore.retention` declares a
    ``max_values`` ceiling — evicts to stay within that ceiling.  Lineage
    outlives the value plane by design, so a ``KnotLineage`` row keeps naming
    an ``output_hash`` whose bytes are gone.  That is the same end state as a
    value scrubbed past its TTL, and it is reported the same way: the read
    *fails*, and never returns ``None`` or a default that a caller could
    mistake for a legitimate stored value.

    It subclasses ``KeyError`` because that is the read contract every
    ``DataStore`` documents, so existing ``except KeyError`` handlers keep
    working unchanged.  It is a distinct type because the two absences have
    different fixes: a hash that was never written is a wiring bug or the
    wrong store, while an evicted hash means this store's ceiling is too low
    for the work it is being asked to do.  Guessing between them is exactly
    what the caller should not have to do.

    Attributes:
        content_hash: The hash whose value was evicted.
        max_values: The ceiling that forced the eviction.
    """

    def __init__(self, *, content_hash: str, max_values: int, store_name: str) -> None:
        """Describe an eviction in terms the caller can act on.

        Args:
            content_hash: The hash that was asked for.
            max_values: The retained-value ceiling in force when it was
                dropped.
            store_name: Class name of the store that evicted it.
        """
        message = (
            f"{store_name}: no value is stored under {content_hash!r} — it was "
            f"evicted to stay within this store's retained-value ceiling of "
            f"{max_values}. Raise the ceiling (`max_values=`) or use a durable "
            f"DataStore if this value has to outlive that window."
        )
        super().__init__(message)
        self._message = message
        self._content_hash = content_hash
        self._max_values = max_values

    def __str__(self) -> str:
        """Return the plain message.

        ``KeyError.__str__`` renders ``repr(args[0])``, which would wrap this
        sentence in quotes wherever it is logged.  The ``KeyError`` base is
        here for the ``except`` clause, not for its formatting.
        """
        return self._message

    @property
    def content_hash(self) -> str:
        return self._content_hash

    @property
    def max_values(self) -> int:
        return self._max_values
