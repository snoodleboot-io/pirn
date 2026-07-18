"""``Cassette`` — a serialisable, ordered collection of recorded I/O entries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.determinism.cassette_entry import CassetteEntry


@dataclass(frozen=True)
class Cassette(PirnOpaqueValue):
    """An immutable tape of :class:`CassetteEntry` values, in record order.

    A cassette is pure data: it round-trips through :meth:`to_payload` /
    :meth:`from_payload` with no loss, so a recorded suite persists to a store and
    replays byte-for-byte later. Mutation is functional — :meth:`with_entry`
    returns a new cassette — leaving replay cursors to the recorder.

    Attributes
    ----------
    entries:
        The recorded interactions, oldest first.
    """

    entries: tuple[CassetteEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise TypeError(f"Cassette: entries must be a tuple, got {type(self.entries).__name__}")
        for entry in self.entries:
            if not isinstance(entry, CassetteEntry):
                raise TypeError(
                    f"Cassette: every entry must be a CassetteEntry, got {type(entry).__name__}"
                )

    @property
    def is_empty(self) -> bool:
        """Return ``True`` when the cassette holds no entries."""
        return len(self.entries) == 0

    def keys(self) -> tuple[str, ...]:
        """Return the distinct entry keys, in first-seen order."""
        seen: dict[str, None] = {}
        for entry in self.entries:
            seen.setdefault(entry.key, None)
        return tuple(seen)

    def entries_for(self, key: str) -> tuple[CassetteEntry, ...]:
        """Return the entries recorded under ``key``, in record order."""
        return tuple(entry for entry in self.entries if entry.key == key)

    def with_entry(self, entry: CassetteEntry) -> Cassette:
        """Return a new cassette with ``entry`` appended.

        Raises:
            TypeError: If ``entry`` is not a CassetteEntry.
        """
        if not isinstance(entry, CassetteEntry):
            raise TypeError(
                f"Cassette.with_entry: entry must be a CassetteEntry, got {type(entry).__name__}"
            )
        return Cassette(entries=(*self.entries, entry))

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping capturing every entry."""
        return {"entries": [entry.to_payload() for entry in self.entries]}

    @classmethod
    def from_payload(cls, payload: Any) -> Cassette:
        """Reconstruct a cassette from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"Cassette.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        raw: Sequence[Any] = payload.get("entries", ())
        return cls(entries=tuple(CassetteEntry.from_payload(item) for item in raw))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
