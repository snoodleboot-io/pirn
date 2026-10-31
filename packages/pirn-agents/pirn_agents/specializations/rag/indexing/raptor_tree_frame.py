"""``RaptorTreeFrame`` — content-address metadata for a :class:`RaptorTree`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RaptorTreeFrame(PirnOpaqueValue):
    """Descriptor facts for a built RAPTOR tree.

    The frame half of the ``Payload[RaptorTreeFrame, RaptorNode | None]``
    split (PIR-868 pattern, applied by PIR-874).

    Attributes
    ----------
    content_hash:
        SHA-256 (truncated) of the leaf corpus; the tree's content address.
    node_count:
        Total number of tree nodes (leaves + summaries) stored.
    level_count:
        Number of levels, including the leaf level.
    reused:
        ``True`` when the build was skipped because an identical tree already
        existed in the store.
    """

    content_hash: str
    node_count: int
    level_count: int
    reused: bool

    def __post_init__(self) -> None:
        if not isinstance(self.content_hash, str) or not self.content_hash:
            raise TypeError(
                f"RaptorTree: content_hash must be a non-empty str, got {self.content_hash!r}"
            )
        if not isinstance(self.node_count, int) or isinstance(self.node_count, bool):
            raise TypeError(
                f"RaptorTree: node_count must be an int, got {type(self.node_count).__name__}"
            )
        if self.node_count < 0:
            raise ValueError(f"RaptorTree: node_count must be >= 0, got {self.node_count!r}")
        if not isinstance(self.level_count, int) or isinstance(self.level_count, bool):
            raise TypeError(
                f"RaptorTree: level_count must be an int, got {type(self.level_count).__name__}"
            )
        if self.level_count < 0:
            raise ValueError(f"RaptorTree: level_count must be >= 0, got {self.level_count!r}")
        if not isinstance(self.reused, bool):
            raise TypeError(f"RaptorTree: reused must be a bool, got {type(self.reused).__name__}")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "content_hash": self.content_hash,
            "node_count": self.node_count,
            "level_count": self.level_count,
            "reused": self.reused,
        }
