"""``ProbabilisticLinker`` — Fellegi-Sunter probabilistic record linkage.

For each candidate pair (from two lists of records), the knot computes a
composite match weight by summing per-field log-likelihood ratios derived
from caller-supplied m/u probabilities.  Pairs are then classified as
``match``, ``non_match``, or ``review`` using configurable weight thresholds.

The result is a list of dicts with keys:
  * ``left_index`` / ``right_index`` — original row indices
  * ``weight``                       — composite match weight (float)
  * ``classification``               — ``"match"`` | ``"review"`` | ``"non_match"``

Algorithm:
    1. Receive resolved ``left_rows``, ``right_rows``, ``field_specs``,
       ``match_threshold``, and ``review_threshold`` in ``process()``.
    2. Validate all inputs: field specs (column identifiers, m/u probability
       ranges), and threshold ordering.
    3. For every left x right pair, compute the composite Fellegi-Sunter
       match weight as the sum of per-field log-likelihood ratios.
    4. Classify each pair: weight >= match_threshold → "match";
       weight >= review_threshold → "review"; otherwise "non_match".
    5. Return a list of classification dicts.

Math:
    Per-field weight (agree): $w_i^+ = \\log_2\\frac{m_i}{u_i}$

    Per-field weight (disagree): $w_i^- = \\log_2\\frac{1 - m_i}{1 - u_i}$

    Composite weight: $W = \\sum_i w_i$

References:
    [1] Fellegi, I.P. & Sunter, A.B. (1969). *A Theory for Record Linkage*.
        JASA 64(328):1183-1210.
    [2] pirn — IdentifierValidator:
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

import math
from typing import Any

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
        field_specs: Knot | Any,
        match_threshold: Knot | float,
        review_threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            left_rows=left_rows,
            right_rows=right_rows,
            field_specs=field_specs,
            match_threshold=match_threshold,
            review_threshold=review_threshold,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _weight(
        field_specs: list[dict[str, Any]],
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> float:
        total = 0.0
        for spec in field_specs:
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
        *,
        left_rows: Any,
        right_rows: Any,
        field_specs: Any,
        match_threshold: Any,
        review_threshold: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
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
        if not isinstance(match_threshold, (int, float)):
            raise TypeError(
                "ProbabilisticLinker: match_threshold must be a number"
            )
        if not isinstance(review_threshold, (int, float)):
            raise TypeError(
                "ProbabilisticLinker: review_threshold must be a number"
            )
        if match_threshold <= review_threshold:
            raise ValueError(
                "ProbabilisticLinker: match_threshold must be > review_threshold"
            )
        field_specs_list = list(field_specs)
        results: list[dict[str, Any]] = []
        for li, left in enumerate(left_rows):
            for ri, right in enumerate(right_rows):
                w = ProbabilisticLinker._weight(field_specs_list, left, right)
                if w >= match_threshold:
                    cls = "match"
                elif w >= review_threshold:
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
