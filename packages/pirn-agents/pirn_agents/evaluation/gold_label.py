"""``GoldLabel`` — a human-scored rubric example for judge calibration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.evaluation.rubric_criterion import RubricCriterion


@dataclass(frozen=True)
class GoldLabel(PirnOpaqueValue):
    """One gold-standard rubric judgement to calibrate an :class:`LLMJudge` against.

    Attributes
    ----------
    prompt:
        The task/prompt the response answered.
    response:
        The response that was judged.
    criteria:
        The rubric criteria the judge should score (drives the judged overall).
    expected_score:
        The human/reference overall score in ``[0, 1]`` the judge is compared to.
    """

    prompt: str
    response: str
    criteria: tuple[RubricCriterion, ...]
    expected_score: float

    def __post_init__(self) -> None:
        """Validate field types and normalise ``criteria`` to a tuple.

        Raises:
            TypeError: If ``prompt``/``response`` are not strings, ``criteria``
                is not a sequence of :class:`RubricCriterion`, or
                ``expected_score`` is not a real number.
        """
        if not isinstance(self.prompt, str):
            raise TypeError(f"GoldLabel.prompt must be a str, got {type(self.prompt).__name__}")
        if not isinstance(self.response, str):
            raise TypeError(f"GoldLabel.response must be a str, got {type(self.response).__name__}")
        if isinstance(self.criteria, (str, bytes)) or not isinstance(self.criteria, Sequence):
            raise TypeError(
                f"GoldLabel.criteria must be a sequence of RubricCriterion, "
                f"got {type(self.criteria).__name__}"
            )
        criteria = tuple(self.criteria)
        for index, criterion in enumerate(criteria):
            if not isinstance(criterion, RubricCriterion):
                raise TypeError(
                    f"GoldLabel.criteria[{index}] must be a RubricCriterion, "
                    f"got {type(criterion).__name__}"
                )
        object.__setattr__(self, "criteria", criteria)
        if isinstance(self.expected_score, bool) or not isinstance(
            self.expected_score, (int, float)
        ):
            raise TypeError(
                f"GoldLabel.expected_score must be a real number, "
                f"got {type(self.expected_score).__name__}"
            )
        object.__setattr__(self, "expected_score", float(self.expected_score))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "response": self.response,
            "criteria": [c._pirn_audit_dict() for c in self.criteria],
            "expected_score": self.expected_score,
        }
