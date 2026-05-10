"""``DICOMPayload`` — DICOM series metadata bundled with its staged filesystem path.

``series`` carries the DICOM lineage metadata; ``data`` is the local
directory where the DICOM files for this series have been staged by the
ingestor.  Both fields travel together through the transport layer so
downstream knots (e.g. NIfTIConverter) receive the full picture in one input.
"""

from __future__ import annotations

from pirn.core.payload import Payload
from pirn.domains.health.types.dicom_series import DICOMSeries


class DICOMPayload(Payload[DICOMSeries, str]):
    """DICOM series: metadata + staged directory path."""

    @property
    def series(self) -> DICOMSeries:
        return self._metadata

    @property
    def dicom_dir(self) -> str:
        return self._data
