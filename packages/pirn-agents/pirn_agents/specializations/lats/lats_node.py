"""``LatsNode`` — one node (a scored action trajectory) in the LATS search tree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class LatsNode(PirnOpaqueValue):
    """A node in the LATS search tree.

    Attributes
    ----------
    trajectory:
        The ordered sequence of actions taken from the root to this node.
    value:
        The value model's estimate for ``trajectory`` (higher is better).
    depth:
        The trajectory length (root is depth 0).
    """

    trajectory: tuple[str, ...]
    value: float
    depth: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "trajectory": list(self.trajectory),
            "value": self.value,
            "depth": self.depth,
        }
