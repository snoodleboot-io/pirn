"""``DocumentOutcomeFrame`` — delta-count metadata for a :class:`DocumentOutcome`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class DocumentOutcomeFrame(PirnOpaqueValue):
    """Run-level facts for one document's ingestion.

    The frame half of the ``Payload[DocumentOutcomeFrame, str]`` split
    (PIR-868 pattern, applied by PIR-874).

    Attributes
    ----------
    embedded:
        Chunks newly embedded and stored.
    unchanged:
        Chunks already present and left untouched.
    removed:
        Stale chunks removed from the store.
    error:
        The isolated failure message, or ``None`` on success.
    """

    embedded: int = 0
    unchanged: int = 0
    removed: int = 0
    error: str | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "embedded": self.embedded,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "error": self.error,
        }
