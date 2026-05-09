"""``DICOMPayload`` — DICOM series metadata bundled with its staged filesystem path.

``series`` carries the DICOM lineage metadata; ``dicom_dir`` is the local
directory where the DICOM files for this series have been staged by the
ingestor.  Both fields travel together through the transport layer so
downstream knots (e.g. NIfTIConverter) receive the full picture in one input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.health.types.dicom_series import DICOMSeries


@dataclass
class DICOMPayload(PirnOpaqueValue):
    """DICOM series: metadata + staged directory path."""

    series: DICOMSeries
    dicom_dir: str

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            **self.series._pirn_audit_dict(),
            "dicom_dir": self.dicom_dir,
        }
