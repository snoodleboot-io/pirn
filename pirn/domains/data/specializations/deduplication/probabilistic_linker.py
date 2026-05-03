"""``ProbabilisticLinker`` — Fellegi-Sunter probabilistic record linkage.

For each candidate pair (from two lists of records), the knot computes a
composite match weight by summing per-field log-likelihood ratios derived
from caller-supplied m/u probabilities.  Pairs are then classified as
``match``, ``non_match``, or ``review`` using configurable weight thresholds.

The result is a list of dicts with keys:
  * ``left_index`` / ``right_index`` — original row indices
  * ``weight``                       — composite match weight (float)
  * ``classification``               — ``"match"`` | ``"review"`` | ``"non_match"``
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class ProbabilisticLinker(Knot):
    """Classify record pairs as match/review/non-match via Fellegi-Sunter weights."""

    def __init__(
        self,
        *,
        left_rows: Knot,
        right_rows: Knot,
        field_specs: Sequence[dict[str, Any]],
        match_threshold: float = 3.0,
        review_threshold: float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Initialise the linker.

        Args:
            left_rows:        Left-side records knot.
            right_rows:       Right-side records knot.
            field_specs:      List of dicts, each with keys:
                              ``column`` (str), ``m`` (float in (0,1)),
                              ``u`` (float in (0,1)).
            match_threshold:  Weight above which a pair is a match.
            review_threshold: Weight above which (and <= match_threshold) a
                              pair is flagged for review.
        """
        for spec in field_specs:
            col = spec.get("column", "")
            IdentifierValidator.validate_column("field_specs[column]", col)
            for prob_key in ("m", "u"):
                val = spec.get(prob_key)
                if not isinstance(val, (int, float)) or not (0.0 < val < 1.0):
                    raise ValueError(
                        f"ProbabilisticLinker: field_specs[{col}][{prob_key!r}] "
                        "must be a float in (0, 1)"
                    )
        if match_threshold <= review_threshold:
            raise ValueError(
                "ProbabilisticLinker: match_threshold must be > review_threshold"
            )
        self._field_specs = list(field_specs)
        self._match_threshold = match_threshold
        self._review_threshold = review_threshold
        super().__init__(
            left_rows=left_rows, right_rows=right_rows, _config=_config, **kwargs
        )

    def _weight(
        self, left: dict[str, Any], right: dict[str, Any]
    ) -> float:
        total = 0.0
        for spec in self._field_specs:
            col: str = spec["column"]
            m: float = spec["m"]
            u: float = spec["u"]
            agree = left.get(col) == right.get(col) and left.get(col) is not None
            if agree:
                total += math.log2(m / u)
            else:
                total += math.log2((1.0 - m) / (1.0 - u))
        return total

    async def process(
        self,
        left_rows: list[dict[str, Any]],
        right_rows: list[dict[str, Any]],
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Compare every left×right pair and classify by Fellegi-Sunter weight.

        Args:
            left_rows:  Left-side records.
            right_rows: Right-side records.

        Returns:
            List of dicts with ``left_index``, ``right_index``, ``weight``,
            and ``classification`` for every pair.
        """
        results: list[dict[str, Any]] = []
        for li, left in enumerate(left_rows):
            for ri, right in enumerate(right_rows):
                w = self._weight(left, right)
                if w >= self._match_threshold:
                    cls = "match"
                elif w >= self._review_threshold:
                    cls = "review"
                else:
                    cls = "non_match"
                results.append(
                    {
                        "left_index": li,
                        "right_index": ri,
                        "weight": w,
                        "classification": cls,
                    }
                )
        return results
