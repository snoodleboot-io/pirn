"""``ADaMDatasetBuilder`` — build CDISC ADaM-style derived datasets.

Production version emits ADaM (Analysis Data Model) datasets such as
``ADSL``, ``ADAE``, or ``ADTTE`` from raw SDTM records using vendor
derivation libraries. This stub applies a caller-supplied
``derived_column -> source_field`` mapping and pipes through the
trial-id and subject-id keys.

Algorithm:
    1. Validate target_dataset and derivations mapping.
    2. For each trial record, apply the derivations to build a row dict.
    3. Return the rows as a tuple.

Math:
    Projection of record *r* to derived column *d*:

    $$\\text{row}[d] = r.\\text{source\\_field}(d)$$

References:
    - CDISC. (2021). Analysis Data Model (ADaM) Implementation Guide v1.3.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.clinical_trial_record import ClinicalTrialRecord


class ADaMDatasetBuilder(Knot):
    """Project trial records into an ADaM-style row tuple."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[ClinicalTrialRecord],
        target_dataset: Knot | str,
        derivations: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            target_dataset=target_dataset,
            derivations=derivations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        target_dataset: str,
        derivations: Mapping[str, str],
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Apply the derivations mapping to each trial record and return ADaM-style row dicts.

        Args:
            records: Sequence of ClinicalTrialRecord objects to project.
            target_dataset: Non-empty name of the target ADaM dataset.
            derivations: Non-empty mapping of derived column name to source field name.

        Returns:
            Tuple of dicts with trial_id, subject_id, and all configured derived columns.

        Raises:
            ValueError: If target_dataset is empty or derivations is empty/has invalid keys.
            TypeError: If derivations is not a Mapping.
        """
        if not isinstance(target_dataset, str) or not target_dataset:
            raise ValueError("ADaMDatasetBuilder: target_dataset must be a non-empty string")
        if not isinstance(derivations, Mapping):
            raise TypeError("ADaMDatasetBuilder: derivations must be a Mapping")
        if len(derivations) == 0:
            raise ValueError("ADaMDatasetBuilder: derivations must be a non-empty mapping")
        for derived_column, source_field in derivations.items():
            if not isinstance(derived_column, str) or not derived_column:
                raise ValueError("ADaMDatasetBuilder: derivation keys must be non-empty strings")
            if not isinstance(source_field, str) or not source_field:
                raise ValueError("ADaMDatasetBuilder: derivation values must be non-empty strings")
        rows: list[Mapping[str, Any]] = []
        for record in records:
            row: dict[str, Any] = {
                "trial_id": record.trial_id,
                "subject_id": record.subject_id,
            }
            for derived_column, source_field in derivations.items():
                row[derived_column] = getattr(record, source_field, None)
            rows.append(row)
        return tuple(rows)
