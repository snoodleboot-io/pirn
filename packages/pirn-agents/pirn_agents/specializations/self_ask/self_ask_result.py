"""``SelfAskResult`` — the typed outcome of a Self-Ask run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SelfAskResult(PirnOpaqueValue):
    """Outcome of a Self-Ask decomposition.

    Attributes
    ----------
    final_answer:
        The composed final answer.
    subquestions:
        The sub-questions the task was decomposed into, in order.
    subanswers:
        The answer to each sub-question, aligned with ``subquestions``.
    """

    final_answer: str
    subquestions: tuple[str, ...]
    subanswers: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "final_answer": self.final_answer,
            "subquestions": list(self.subquestions),
            "subanswers": list(self.subanswers),
        }
