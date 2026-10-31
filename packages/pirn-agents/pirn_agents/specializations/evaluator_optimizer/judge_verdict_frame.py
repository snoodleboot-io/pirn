"""``JudgeVerdictFrame`` — the scored half of a :class:`JudgeVerdict` (PIR-868, PIR-874)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class JudgeVerdictFrame(PirnOpaqueValue):
    """The numeric judgment of a candidate answer.

    The frame half of the ``Payload[JudgeVerdictFrame, str]`` split.

    Attributes
    ----------
    score:
        Quality score on a 0-10 scale (higher is better).
    """

    score: float

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"score": self.score}
