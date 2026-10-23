"""``LatsNodeFrame`` — lineage metadata for a :class:`LatsNode`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class LatsNodeFrame(PirnOpaqueValue):
    """Run-level facts about one node of the LATS search tree.

    The frame half of the ``Payload[LatsNodeFrame, tuple[str, ...]]`` split
    (PIR-874, following PIR-868): what the search *knows about* a trajectory,
    as opposed to the trajectory itself.

    Attributes
    ----------
    value:
        The value model's estimate for the trajectory (higher is better).
    depth:
        The trajectory length (root is depth 0).
    """

    value: float
    depth: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"value": self.value, "depth": self.depth}
