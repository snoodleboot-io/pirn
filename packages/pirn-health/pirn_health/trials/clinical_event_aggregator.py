"""``ClinicalEventAggregator`` — count per-subject clinical events.

Production version computes per-subject summaries (counts, first/last
dates, durations) for whichever event codes the analysis plan calls
for. This stub returns just the counts: per-subject, per-event-code,
filtered to the configured ``event_codes``.

Algorithm:
    1. Validate event_codes sequence.
    2. For each record, increment the count for each matching event code.
    3. Return the per-subject, per-event-code count mapping.

Math:
    Count for subject *s* and code *c*:

    $$n_{s,c} = |\\{r \\in R : r.\\text{subject} = s,\\, c \\in r.\\text{obs\\_codes}\\}|$$

References:
    - CDISC. (2022). Clinical Data Interchange Standards Consortium SDTM IG v3.4.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.clinical_trial_record import ClinicalTrialRecord


class ClinicalEventAggregator(Knot):
    """Aggregate trial-event counts per subject and per event code."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[ClinicalTrialRecord],
        event_codes: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, event_codes=event_codes, _config=_config, **kwargs)

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        event_codes: Sequence[str],
        **_: Any,
    ) -> Mapping[str, Mapping[str, int]]:
        """Count per-subject occurrences of each configured event code.

        Args:
            records: Sequence of ClinicalTrialRecord objects to aggregate.
            event_codes: Non-empty sequence of event code strings to track.

        Returns:
            Mapping of subject_id to a dict of event_code to occurrence count.

        Raises:
            TypeError: If event_codes is not a list or tuple.
            ValueError: If event_codes is empty or contains non-string items.
        """
        if not isinstance(event_codes, (list, tuple)):
            raise TypeError("ClinicalEventAggregator: event_codes must be a list or tuple")
        if len(event_codes) == 0:
            raise ValueError("ClinicalEventAggregator: event_codes must be non-empty")
        for code in event_codes:
            if not isinstance(code, str) or not code:
                raise ValueError(
                    "ClinicalEventAggregator: every event_code must be a non-empty string"
                )
        codes = set(event_codes)
        counts: dict[str, dict[str, int]] = {}
        for record in records:
            subject = record.subject_id
            if subject not in counts:
                counts[subject] = {code: 0 for code in event_codes}
            for code in record.observation_codes:
                if code in codes:
                    counts[subject][code] += 1
        return {subject: dict(by_code) for subject, by_code in counts.items()}
