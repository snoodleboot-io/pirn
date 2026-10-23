"""``SeedLookupFrame`` — lineage metadata for a :class:`SeedLookup`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SeedLookupFrame(PirnOpaqueValue):
    """What one seed read asked for and whether the store had it.

    Attributes
    ----------
    node_id:
        The seed id that was looked up.
    found:
        Whether the store holds a node under that id.
    """

    node_id: str
    found: bool

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "found": self.found}
