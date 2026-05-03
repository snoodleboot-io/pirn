"""``ADaMDatasetBuilder`` — build CDISC ADaM-style derived datasets.

Production version emits ADaM (Analysis Data Model) datasets such as
``ADSL``, ``ADAE``, or ``ADTTE`` from raw SDTM records using vendor
derivation libraries. This stub applies a caller-supplied
``derived_column -> source_field`` mapping and pipes through the
trial-id and subject-id keys.
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
        records: Knot,
        target_dataset: str,
        derivations: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(records, Knot):
            raise TypeError("ADaMDatasetBuilder: records must be a Knot")
        if not isinstance(target_dataset, str) or not target_dataset:
            raise ValueError(
                "ADaMDatasetBuilder: target_dataset must be a non-empty string"
            )
        if not isinstance(derivations, Mapping):
            raise TypeError(
                "ADaMDatasetBuilder: derivations must be a Mapping"
            )
        if len(derivations) == 0:
            raise ValueError(
                "ADaMDatasetBuilder: derivations must be a non-empty mapping"
            )
        for derived_column, source_field in derivations.items():
            if not isinstance(derived_column, str) or not derived_column:
                raise ValueError(
                    "ADaMDatasetBuilder: derivation keys must be non-empty strings"
                )
            if not isinstance(source_field, str) or not source_field:
                raise ValueError(
                    "ADaMDatasetBuilder: derivation values must be non-empty strings"
                )
        self._target_dataset = target_dataset
        self._derivations = dict(derivations)
        super().__init__(records=records, _config=_config, **kwargs)

    @property
    def target_dataset(self) -> str:
        return self._target_dataset

    async def process(
        self,
        records: Sequence[ClinicalTrialRecord],
        **_: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        """Apply the derivations mapping to each trial record and return ADaM-style row dicts.

        Args:
            records: Sequence of ClinicalTrialRecord objects to project.

        Returns:
            Tuple of dicts with trial_id, subject_id, and all configured derived columns.
        """
        rows: list[Mapping[str, Any]] = []
        for record in records:
            row: dict[str, Any] = {
                "trial_id": record.trial_id,
                "subject_id": record.subject_id,
            }
            for derived_column, source_field in self._derivations.items():
                row[derived_column] = getattr(record, source_field, None)
            rows.append(row)
        return tuple(rows)
