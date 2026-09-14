"""``FallbackFrame`` — lineage metadata for a :class:`FallbackResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class FallbackFrame(PirnOpaqueValue):
    """Run-level facts for a confidence-ordered fallback-chain dispatch.

    The frame half of the ``Payload[FallbackFrame, ToolResult | None]`` split
    (PIR-868).

    Attributes
    ----------
    succeeded:
        Whether some candidate returned a successful :class:`ToolResult`.
    chosen:
        The name of the candidate that succeeded, or ``None`` on exhaustion.
    attempted:
        Names of candidates actually invoked, in order.
    skipped:
        Names of candidates skipped because their confidence was below their
        ``min_confidence`` floor.
    """

    succeeded: bool
    chosen: str | None
    attempted: tuple[str, ...]
    skipped: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "chosen": self.chosen,
            "attempted": list(self.attempted),
            "skipped": list(self.skipped),
        }
