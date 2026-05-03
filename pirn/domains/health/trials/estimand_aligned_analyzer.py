"""``EstimandAlignedAnalyzer`` — filter records to an estimand strategy.

The ICH E9(R1) addendum defines five estimand strategies for handling
intercurrent events: treatment-policy, hypothetical, while-on-treatment,
principal-stratum, and composite-strategy. Production deployments
apply strategy-specific imputation and exclusion rules; this stub
implements the simplest record-level filter consistent with each
strategy.
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
        records: Knot,
        strategy: str,
        intercurrent_event_codes: Sequence[str] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, Knot):
            raise TypeError(
                "EstimandAlignedAnalyzer: records must be a Knot"
            )
        if not isinstance(strategy, str):
            raise TypeError(
                "EstimandAlignedAnalyzer: strategy must be a string"
            )
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
        self._strategy = strategy
        self._intercurrent_codes = frozenset(intercurrent_event_codes)
        super().__init__(records=records, _config=_config, **kwargs)

    @property
    def strategy(self) -> str:
        return self._strategy

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        **_: Any,
    ) -> tuple[ClinicalTrialRecord, ...]:
        """Filter trial records according to the configured estimand strategy and return the qualifying records.

        Args:
            records: Sequence of ClinicalTrialRecord objects to filter.

        Returns:
            Tuple of ClinicalTrialRecord objects that satisfy the estimand strategy.

        Raises:
            RuntimeError: If an unexpected strategy value bypasses the __init__ guard.
        """
        if self._strategy in ("treatment-policy", "composite-strategy"):
            return tuple(records)
        if self._strategy == "principal-stratum":
            return tuple(records)
        if self._strategy == "while-on-treatment":
            return tuple(
                record
                for record in records
                if not self._has_intercurrent_event(record)
            )
        if self._strategy == "hypothetical":
            return tuple(
                record
                for record in records
                if not self._has_intercurrent_event(record)
            )
        # Defensive — strategy was validated in __init__.
        raise RuntimeError(
            f"EstimandAlignedAnalyzer: unhandled strategy {self._strategy!r}"
        )

    def _has_intercurrent_event(self, record: ClinicalTrialRecord) -> bool:
        if not self._intercurrent_codes:
            return False
        return any(
            code in self._intercurrent_codes for code in record.observation_codes
        )
