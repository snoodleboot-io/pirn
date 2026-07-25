"""``RubricCriterion`` — one weighted dimension of a scoring rubric."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RubricCriterion(PirnOpaqueValue):
    """A single named dimension the judge scores a response against.

    Attributes
    ----------
    name:
        Short identifier for the criterion (e.g. ``"correctness"``).
    description:
        Human/judge-facing description of what a high score means.
    weight:
        Relative importance in the weighted overall score; must be > 0.
    """

    name: str
    description: str = ""
    weight: float = 1.0

    def __post_init__(self) -> None:
        """Validate the criterion's fields.

        Raises:
            TypeError: If ``name``/``description`` are not strings or ``weight``
                is not a real number.
            ValueError: If ``weight`` is not strictly positive.
        """
        if not isinstance(self.name, str):
            raise TypeError(f"RubricCriterion.name must be a str, got {type(self.name).__name__}")
        if not isinstance(self.description, str):
            raise TypeError(
                f"RubricCriterion.description must be a str, got {type(self.description).__name__}"
            )
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise TypeError(
                f"RubricCriterion.weight must be a real number, got {type(self.weight).__name__}"
            )
        if self.weight <= 0:
            raise ValueError(f"RubricCriterion.weight must be > 0, got {self.weight}")
        object.__setattr__(self, "weight", float(self.weight))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "weight": self.weight}
