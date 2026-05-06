"""``EstimandAlignedAnalyzer`` — filter records to an estimand strategy.

The ICH E9(R1) addendum defines five estimand strategies for handling
intercurrent events: treatment-policy, hypothetical, while-on-treatment,
principal-stratum, and composite-strategy. Production deployments
apply strategy-specific imputation and exclusion rules; this stub
implements the simplest record-level filter consistent with each
strategy.

Algorithm:
    1. Validate strategy and intercurrent_event_codes.
    2. Filter records according to the chosen estimand strategy.
    3. Return the qualifying records as a tuple.

Math:
    For while-on-treatment and hypothetical strategies, records with
    intercurrent events are excluded:

    $$S = \\{r \\in R : \\text{obs\\_codes}(r) \\cap C_{IE} = \\emptyset\\}$$

    where $C_{IE}$ is the set of intercurrent event codes.

References:
    - ICH E9(R1). (2019). Addendum on Estimands and Sensitivity Analysis in Clinical Trials.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord


class EstimandAlignedAnalyzer(Knot):
    """Project trial records onto a chosen estimand strategy."""

    _supported_strategies: frozenset[str] = frozenset(
        {
            "treatment-policy",
            "hypothetical",
            "while-on-treatment",
            "principal-stratum",
            "composite-strategy",
        }
    )

    def __init__(
        self,
        *,
        records: Knot | Sequence[ClinicalTrialRecord],
        strategy: Knot | str,
        intercurrent_event_codes: Knot | Sequence[str] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            strategy=strategy,
            intercurrent_event_codes=intercurrent_event_codes,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        strategy: str,
        intercurrent_event_codes: Sequence[str] = (),
        **_: Any,
    ) -> tuple[ClinicalTrialRecord, ...]:
        """Filter trial records according to the estimand strategy.

        Args:
            records: Sequence of ClinicalTrialRecord objects to filter.
            strategy: One of 'treatment-policy', 'hypothetical', 'while-on-treatment',
                'principal-stratum', 'composite-strategy'.
            intercurrent_event_codes: Sequence of intercurrent event codes.

        Returns:
            Tuple of ClinicalTrialRecord objects that satisfy the estimand strategy.

        Raises:
            TypeError: If strategy is not a string or intercurrent_event_codes is not a sequence.
            ValueError: If strategy is not supported.
        """
        if not isinstance(strategy, str):
            raise TypeError("EstimandAlignedAnalyzer: strategy must be a string")
        if strategy not in self._supported_strategies:
            raise ValueError(
                f"EstimandAlignedAnalyzer: strategy {strategy!r} not supported; "
                f"choose from {sorted(self._supported_strategies)!r}"
            )
        if not isinstance(intercurrent_event_codes, (list, tuple)):
            raise TypeError(
                "EstimandAlignedAnalyzer: intercurrent_event_codes must be list or tuple"
            )
        for code in intercurrent_event_codes:
            if not isinstance(code, str) or not code:
                raise ValueError(
                    "EstimandAlignedAnalyzer: intercurrent_event_codes must be non-empty strings"
                )
        intercurrent_set = frozenset(intercurrent_event_codes)
        if strategy in ("treatment-policy", "composite-strategy"):
            return tuple(records)
        if strategy == "principal-stratum":
            return tuple(records)
        if strategy in ("while-on-treatment", "hypothetical"):
            return tuple(
                record
                for record in records
                if not self._has_intercurrent_event(record, intercurrent_set)
            )
        raise RuntimeError(f"EstimandAlignedAnalyzer: unhandled strategy {strategy!r}")

    @staticmethod
    def _has_intercurrent_event(
        record: ClinicalTrialRecord, intercurrent_codes: frozenset[str]
    ) -> bool:
        if not intercurrent_codes:
            return False
        return any(code in intercurrent_codes for code in record.observation_codes)
