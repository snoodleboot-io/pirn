from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.value_retention import ValueRetention
from pirn.exceptions.value_evicted_error import ValueEvictedError


class InMemoryDataStore(DataStore):
    """In-memory DataStore.

    Holds intermediate values keyed by content hash.  Scrubbing is
    immediate and irreversible.

    Being ephemeral, it keeps a **bounded** working set: past ``max_values``
    the least recently used value is evicted.  The bound is declared via
    :attr:`retention` rather than inferred from the class, so a caller that
    would otherwise grow the value plane without limit can write to it safely.
    ``LoopSubTapestry`` is the case that needs this — an open-ended
    conversational loop produces a fresh set of values every turn, and since
    PIR-837 those land in the outer tapestry's store rather than in a
    throwaway one.  See PIR-839.

    The default ceiling is high enough that ordinary pipelines never reach it;
    it is a guard against unbounded growth, not a working-set limit.

    Eviction is **least-recently-used, not oldest-first**, which is where this
    differs from ``InMemoryHistory``.  Runs are a log — the oldest is the one
    you are most willing to lose.  Values are content-addressed operands, and
    age says nothing about whether anything still references them: a loop's
    invariant inputs are written once on turn one and read on every turn
    after.  Recency of *access* is the only signal the store has, so reads
    refresh a value and only genuinely idle values are dropped.

    ``has()`` deliberately does **not** count as an access.  It is a probe,
    and a probe that mutates eviction order would let a bystander keep dead
    values resident.
    """

    #: Default retained-value ceiling.  Sized so normal use never evicts.
    DEFAULT_MAX_VALUES: int = 10_000

    def __init__(self, *, max_values: int | None = None) -> None:
        """Initialise the store.

        Args:
            max_values: Retained-value ceiling.  Defaults to
                :attr:`DEFAULT_MAX_VALUES`.  Pass an explicit value to tighten
                it for a long-running session.

        Raises:
            ValueError: If ``max_values`` is not positive.
        """
        if max_values is not None and max_values <= 0:
            raise ValueError(f"InMemoryDataStore: max_values must be positive, got {max_values!r}")
        self._max_values: int = (
            InMemoryDataStore.DEFAULT_MAX_VALUES if max_values is None else max_values
        )
        self._values: OrderedDict[str, Any] = OrderedDict()
        # Hashes this store evicted, so a later read can say *why* the value
        # is gone instead of leaving the caller to guess between an eviction,
        # a typo and the wrong store.  Bounded by the same ceiling: a
        # tombstone is one hash string, so this keeps the store's footprint
        # O(max_values) rather than reintroducing the growth it exists to
        # report on.  Past that many further evictions a tombstone is itself
        # dropped and the read degrades to a plain `KeyError`.  The read still
        # *fails* — which is the guarantee — it just stops being able to name
        # the reason.
        self._evicted: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()

    @property
    def retention(self) -> ValueRetention:
        """Declare the bounded working set this store keeps."""
        return ValueRetention(max_values=self._max_values)

    async def put(self, content_hash: str, value: Any) -> None:
        """Store a value under its content hash.

        Evicts the least recently used value once the retained count exceeds
        ``max_values``.

        Args:
            content_hash: Content-addressable key for the value.
            value: Arbitrary Python object to store.
        """
        with self._lock:
            self._values[content_hash] = value
            self._values.move_to_end(content_hash)
            # Re-writing a hash makes it present again, so its tombstone is
            # now a lie.  Content addressing guarantees the value is the same
            # one that was evicted.
            self._evicted.pop(content_hash, None)
            self._evict_to_bound()

    async def get(self, content_hash: str) -> Any:
        """Retrieve a value by its content hash, refreshing its recency.

        Args:
            content_hash: Hash previously passed to :meth:`put`.

        Returns:
            The stored Python object.

        Raises:
            ValueEvictedError: If a value was stored under ``content_hash``
                and this store dropped it to stay within ``max_values``.  It
                is a ``KeyError`` subclass.
            KeyError: If no value was ever stored under ``content_hash``, or
                it was explicitly scrubbed.
        """
        with self._lock:
            if content_hash not in self._values:
                if content_hash in self._evicted:
                    raise ValueEvictedError(
                        content_hash=content_hash,
                        max_values=self._max_values,
                        store_name=type(self).__name__,
                    )
                raise KeyError(content_hash)
            self._values.move_to_end(content_hash)
            return self._values[content_hash]

    async def has(self, content_hash: str) -> bool:
        """Return ``True`` if a value is stored under ``content_hash``.

        A probe, not an access: it does not refresh the value's recency, so
        checking for a value cannot keep it alive.

        Args:
            content_hash: Hash to check.

        Returns:
            ``True`` if present, ``False`` otherwise — including when the
            value was evicted, which is indistinguishable from absent by
            design.  Callers that need the distinction read with :meth:`get`
            and catch ``ValueEvictedError``.
        """
        with self._lock:
            return content_hash in self._values

    async def scrub(self, content_hash: str) -> None:
        """Remove the value stored under ``content_hash``, if present.

        Scrubbing is the caller's own decision, so it leaves no eviction
        tombstone: a later read reports a plain missing key rather than
        blaming a ceiling that had nothing to do with it.

        Args:
            content_hash: Hash of the value to remove.
        """
        with self._lock:
            self._values.pop(content_hash, None)
            self._evicted.pop(content_hash, None)

    def _evict_to_bound(self) -> None:
        """Drop least-recently-used values until within ``max_values``.

        Caller must hold ``self._lock``.
        """
        while len(self._values) > self._max_values:
            evicted_hash, _ = self._values.popitem(last=False)
            self._evicted[evicted_hash] = None
            while len(self._evicted) > self._max_values:
                self._evicted.popitem(last=False)
