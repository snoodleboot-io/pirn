"""``DICOMSeries`` — pointer to a DICOM image series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class DICOMSeries(PirnOpaqueValue):
    """Reference to a DICOM image series fetched from PACS."""

    study_uid: str = ""
    series_uid: str = ""
    modality: str = ""
    num_frames: int = 0
    fetched_at: datetime = datetime(1970, 1, 1, tzinfo=UTC)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "study_uid": self.study_uid,
            "series_uid": self.series_uid,
            "modality": self.modality,
            "num_frames": self.num_frames,
            "fetched_at": self.fetched_at.isoformat(),
        }
