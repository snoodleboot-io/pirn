"""A read-only mapping of concurrency group name to in-flight limit."""

from __future__ import annotations

from collections.abc import Iterator, Mapping


class GroupLimits(Mapping[str, int]):
    """Immutable ``{group name: limit}`` that pickles, copies and hashes.

    ``ConcurrencyLimits`` is a frozen value that travels on a ``RunRequest``,
    and a ``RunRequest`` is pickled by queue triggers and process-boundary
    dispatchers and deep-copied by ``model_copy(deep=True)``.  A
    ``types.MappingProxyType`` is read-only but can be neither pickled nor
    deep-copied, so the groups are held here instead: a tuple of pairs, which
    is what pickles, with a private dict built from it for lookups.

    There is no way to add, change or remove an entry after construction.
    """

    __slots__ = ("_index", "_pairs")

    def __init__(self, limits: Mapping[str, int] | None = None) -> None:
        """Copy *limits*; later changes to the source do not show through.

        Args:
            limits: Group name to limit.  ``None`` means no groups.
        """
        pairs = tuple((limits or {}).items())
        self._pairs: tuple[tuple[str, int], ...] = pairs
        self._index: dict[str, int] = dict(pairs)

    def __getitem__(self, group: str) -> int:
        return self._index[group]

    def __iter__(self) -> Iterator[str]:
        return iter(self._index)

    def __len__(self) -> int:
        return len(self._index)

    def __hash__(self) -> int:
        return hash(frozenset(self._pairs))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return self._index == dict(other.items())
        return NotImplemented

    def __repr__(self) -> str:
        return f"GroupLimits({self._index!r})"

    def __reduce__(self) -> tuple[type[GroupLimits], tuple[dict[str, int]]]:
        # Rebuild from a plain dict: the slots hold nothing pickle cannot.
        return (GroupLimits, (dict(self._pairs),))
