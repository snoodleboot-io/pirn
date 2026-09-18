"""``Study`` — the series of DICOM records making up one imaging study.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from examples.domain_formats.medical_triage_agent.dicom_record import DicomRecord
from examples.domain_formats.medical_triage_agent.seeded_rng import SeededRng


@dataclass(frozen=True)
class Study:
    """One imaging study: every series decoded from the same DICOM directory."""

    study_id: str
    records: tuple[DicomRecord, ...]

    @property
    def modality(self) -> str:
        return self.records[0].modality if self.records else "UNKNOWN"

    @property
    def n_pixels(self) -> int:
        return sum(len(r.pixel_data) // 4 for r in self.records)

    @classmethod
    def synthetic(cls, study_id: str, modality: str) -> Study:
        """Build a reproducible stand-in for a study decoded by ``DicomFormat``."""
        rng = SeededRng.for_study(study_id, "build")
        n_series = rng.randint(1, 4)
        records: list[DicomRecord] = []
        for s in range(n_series):
            rows, cols = rng.choice([(512, 512), (256, 256), (1024, 1024)])
            records.append(
                DicomRecord(
                    patient_id=hashlib.sha256(f"pt-{study_id}-{s}".encode()).hexdigest()[:16],
                    modality=modality,
                    study_date="20260502",
                    series_number=s + 1,
                    rows=rows,
                    columns=cols,
                    pixel_data=DicomRecord.synthetic_pixel_data(rows // 8, cols // 8, rng),
                    metadata={"InstitutionName": "General Hospital", "StudyDescription": study_id},
                )
            )
        return cls(study_id=study_id, records=tuple(records))
