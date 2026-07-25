"""``TraceDiff`` — the structured result of diffing two recorded runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class TraceDiff(PirnOpaqueValue):
    """What changed between two runs' trajectories, aligned by step index.

    Each ``changed`` entry is a mapping ``{"index", "before", "after", "fields"}``
    naming which of ``kind`` / ``name`` / ``payload`` diverged at that step;
    ``added`` / ``removed`` list indices present in only one run. ``is_identical``
    is the fast "nothing diverged" check a regression gate needs.

    Attributes
    ----------
    changed:
        Per-index descriptions of steps that differ between the two runs.
    added:
        Indices present only in the second run (it ran longer).
    removed:
        Indices present only in the first run (the second stopped earlier).
    """

    changed: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    added: tuple[int, ...] = field(default_factory=tuple)
    removed: tuple[int, ...] = field(default_factory=tuple)

    @property
    def is_identical(self) -> bool:
        """Return ``True`` when the two traces have no differences."""
        return not self.changed and not self.added and not self.removed

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of the diff."""
        return {
            "changed": [dict(entry) for entry in self.changed],
            "added": list(self.added),
            "removed": list(self.removed),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> TraceDiff:
        """Reconstruct a diff from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"TraceDiff.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        changed: Sequence[Any] = payload.get("changed", ())
        added: Sequence[Any] = payload.get("added", ())
        removed: Sequence[Any] = payload.get("removed", ())
        return cls(
            changed=tuple(dict(entry) for entry in changed),
            added=tuple(int(index) for index in added),
            removed=tuple(int(index) for index in removed),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
