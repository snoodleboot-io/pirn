"""``ClaimSupportFrame`` — verdict metadata for a :class:`ClaimSupport`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ClaimSupportFrame(PirnOpaqueValue):
    """Facts about one claim's lookup in a memory store.

    The frame half of the ``Payload[ClaimSupportFrame, tuple[Mapping[str, Any], ...]]``
    split (PIR-874).

    Attributes
    ----------
    claim:
        The claim that was searched for.
    supported:
        Whether the search returned at least one hit.
    hit_count:
        How many hits the search returned.
    """

    claim: str
    supported: bool
    hit_count: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "supported": self.supported,
            "hit_count": self.hit_count,
        }
