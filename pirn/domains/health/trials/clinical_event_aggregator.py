"""``ClinicalEventAggregator`` — count per-subject clinical events.

Production version computes per-subject summaries (counts, first/last
dates, durations) for whichever event codes the analysis plan calls
for. This stub returns just the counts: per-subject, per-event-code,
filtered to the configured ``event_codes``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord


class ClinicalEventAggregator(Knot):
    """Aggregate trial-event counts per subject and per event code."""

    def __init__(
        self,
        *,
        records: Knot,
        event_codes: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, Knot):
            raise TypeError(
                "ClinicalEventAggregator: records must be a Knot"
            )
        if not isinstance(event_codes, (list, tuple)):
            raise TypeError(
                "ClinicalEventAggregator: event_codes must be a list or tuple"
            )
        if len(event_codes) == 0:
            raise ValueError(
                "ClinicalEventAggregator: event_codes must be non-empty"
            )
        for code in event_codes:
            if not isinstance(code, str) or not code:
                raise ValueError(
                    "ClinicalEventAggregator: every event_code must be a non-empty string"
                )
        self._event_codes = tuple(event_codes)
        super().__init__(records=records, _config=_config, **kwargs)

    @property
    def event_codes(self) -> tuple[str, ...]:
        return self._event_codes

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        **_: Any,
    ) -> Mapping[str, Mapping[str, int]]:
        """Count per-subject occurrences of each configured event code and return a subject-to-code-count mapping.

        Args:
            records: Sequence of ClinicalTrialRecord objects to aggregate.

        Returns:
            Mapping of subject_id to a dict of event_code to occurrence count.
        """
        codes = set(self._event_codes)
        counts: dict[str, dict[str, int]] = {}
        for record in records:
            subject = record.subject_id
            if subject not in counts:
                counts[subject] = {code: 0 for code in self._event_codes}
            for code in record.observation_codes:
                if code in codes:
                    counts[subject][code] += 1
        return {subject: dict(by_code) for subject, by_code in counts.items()}
