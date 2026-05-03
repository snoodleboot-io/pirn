"""``MedDRANormalizer`` — map verbatim adverse-event terms to MedDRA PTs.

Production version queries a licensed MedDRA dictionary to look up
preferred terms (and walks the SOC/HLGT/HLT/PT/LLT hierarchy). This
stub uses a caller-injected ``verbatim -> preferred_term`` mapping and
falls back to the verbatim string when an entry is absent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord


class MedDRANormalizer(Knot):
    """Annotate trial records with MedDRA preferred-term lookups."""

    def __init__(
        self,
        *,
        records: Knot,
        term_to_pt: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, Knot):
            raise TypeError("MedDRANormalizer: records must be a Knot")
        if not isinstance(term_to_pt, Mapping):
            raise TypeError(
                "MedDRANormalizer: term_to_pt must be a Mapping"
            )
        if len(term_to_pt) == 0:
            raise ValueError(
                "MedDRANormalizer: term_to_pt must be a non-empty mapping"
            )
        for verbatim, preferred in term_to_pt.items():
            if not isinstance(verbatim, str) or not verbatim:
                raise ValueError(
                    "MedDRANormalizer: term_to_pt keys must be non-empty strings"
                )
            if not isinstance(preferred, str) or not preferred:
                raise ValueError(
                    "MedDRANormalizer: term_to_pt values must be non-empty strings"
                )
        self._term_to_pt = dict(term_to_pt)
        super().__init__(records=records, _config=_config, **kwargs)

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Look up each record's first observation code in the term map and return annotated rows with meddra_pt.

        Args:
            records: Sequence of ClinicalTrialRecord objects to annotate.

        Returns:
            Tuple of dicts carrying trial_id, subject_id, visit_number,
            observation_codes, observed_at, and the resolved meddra_pt term.
        """
        annotated: list[Mapping[str, Any]] = []
        for record in records:
            # Use the first observation_code as the verbatim term; if no
            # codes are present, the empty string falls through to the
            # fallback path and is returned as the preferred term.
            verbatim = record.observation_codes[0] if record.observation_codes else ""
            preferred = self._term_to_pt.get(verbatim, verbatim)
            annotated.append(
                {
                    "trial_id": record.trial_id,
                    "subject_id": record.subject_id,
                    "visit_number": record.visit_number,
                    "observation_codes": tuple(record.observation_codes),
                    "observed_at": record.observed_at,
                    "meddra_pt": preferred,
                }
            )
        return tuple(annotated)
