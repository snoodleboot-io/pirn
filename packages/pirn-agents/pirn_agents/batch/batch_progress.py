"""``BatchProgress`` — the per-fire summary of a batch run's completed items.

A pure summary value: ``TriggeredBatch`` returns one per fire, naming the item
keys that succeeded out of the total attempted. It checkpoints nothing and is
never read back to decide what to run — resume-after-crash is a ``RunHistory``
lineage query on each item's knot id (``item:<batch_id>:<key>``, see
:class:`~pirn_agents.batch.map_agent.MapAgent`), so the engine's own run record
is the only progress state there is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class BatchProgress(PirnOpaqueValue):
    """The set of item keys one batch run completed, keyed by ``batch_id``.

    Attributes
    ----------
    batch_id:
        The id this run was reported under.
    completed_keys:
        The item keys that finished successfully. Frozen (immutable) so the
        value stays hashable and safe to share.
    total:
        Total item count attempted, when known, else ``None``.
    """

    batch_id: str
    completed_keys: frozenset[str] = frozenset()
    total: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.batch_id, str) or not self.batch_id:
            raise TypeError("BatchProgress: batch_id must be a non-empty str")
        if not isinstance(self.completed_keys, frozenset):
            raise TypeError(
                f"BatchProgress: completed_keys must be a frozenset, "
                f"got {type(self.completed_keys).__name__}"
            )

    @property
    def completed_count(self) -> int:
        """How many items completed."""
        return len(self.completed_keys)

    def is_complete(self, key: str) -> bool:
        """Whether ``key`` completed in this run."""
        return key in self.completed_keys

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this summary."""
        return {
            "batch_id": self.batch_id,
            "completed_keys": sorted(self.completed_keys),
            "total": self.total,
        }

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
