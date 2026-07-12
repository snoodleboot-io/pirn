"""``JudgeVerdict`` — a scored verdict from an LLM-as-judge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class JudgeVerdict(PirnOpaqueValue):
    """A numeric judgment of a candidate answer.

    This is the scored generalisation of the boolean signal
    :class:`~pirn_agents.control.reflection_check.ReflectionCheck` returns: rather
    than a yes/no "iterate again?", the judge returns a continuous ``score`` plus
    ``feedback`` the optimiser can act on.

    Attributes
    ----------
    score:
        Quality score on a 0-10 scale (higher is better).
    feedback:
        Free-form critique the generator can use to improve the next candidate.
    """

    score: float
    feedback: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"score": self.score, "feedback": self.feedback}
