"""``MedDRANormalizer`` — map verbatim adverse-event terms to MedDRA PTs.

Production version queries a licensed MedDRA dictionary to look up
preferred terms (and walks the SOC/HLGT/HLT/PT/LLT hierarchy). This
stub uses a caller-injected ``verbatim -> preferred_term`` mapping and
falls back to the verbatim string when an entry is absent.

Algorithm:
    1. Validate term_to_pt mapping.
    2. For each record, look up the first observation code in the term map.
    3. Return annotated rows with the resolved meddra_pt field.

Math:
    Lookup function:

    $$\\text{pt}(v) = \\begin{cases} M[v] & v \\in M \\\\ v & \\text{otherwise} \\end{cases}$$

    where $M$ is the term-to-preferred-term mapping.

References:
    - MedDRA MSSO. (2023). MedDRA Introductory Guide v26.0.
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
        records: Knot | Sequence[ClinicalTrialRecord],
        term_to_pt: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(records=records, term_to_pt=term_to_pt, _config=_config, **kwargs)

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        term_to_pt: Mapping[str, str],
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Look up each record's first observation code in the term map.

        Args:
            records: Sequence of ClinicalTrialRecord objects to annotate.
            term_to_pt: Non-empty mapping of verbatim term to MedDRA preferred term.

        Returns:
            Tuple of dicts carrying trial_id, subject_id, visit_number,
            observation_codes, observed_at, and the resolved meddra_pt term.

        Raises:
            TypeError: If term_to_pt is not a Mapping.
            ValueError: If term_to_pt is empty or has invalid keys/values.
        """
        if not isinstance(term_to_pt, Mapping):
            raise TypeError("MedDRANormalizer: term_to_pt must be a Mapping")
        if len(term_to_pt) == 0:
            raise ValueError("MedDRANormalizer: term_to_pt must be a non-empty mapping")
        for verbatim, preferred in term_to_pt.items():
            if not isinstance(verbatim, str) or not verbatim:
                raise ValueError("MedDRANormalizer: term_to_pt keys must be non-empty strings")
            if not isinstance(preferred, str) or not preferred:
                raise ValueError("MedDRANormalizer: term_to_pt values must be non-empty strings")
        annotated: list[Mapping[str, Any]] = []
        for record in records:
            verbatim = record.observation_codes[0] if record.observation_codes else ""
            preferred = term_to_pt.get(verbatim, verbatim)
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
