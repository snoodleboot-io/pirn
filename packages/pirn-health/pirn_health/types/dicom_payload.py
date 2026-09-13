"""``DICOMPayload`` — DICOM series metadata bundled with its parsed dataset.

``series`` carries the DICOM lineage metadata; ``data`` is the parsed
``pydicom.Dataset`` for this series, held entirely in memory. Both fields
travel together through the transport layer so downstream knots (e.g.
NIfTIConverter) receive the full picture in one input without the assembler
or disassembler touching the filesystem.

``data`` is typed ``Any`` rather than ``pydicom.Dataset`` because this module
must not import ``pydicom`` at load time (it is an optional dependency of the
``health`` extra); the assembler and disassembler that produce/consume this
payload lazy-import ``pydicom`` inside their methods.
"""

from __future__ import annotations

from typing import Any

from pirn.core.payload import Payload

from pirn_health.types.dicom_series import DICOMSeries


class DICOMPayload(Payload[DICOMSeries, Any]):
    """DICOM series: metadata + parsed ``pydicom.Dataset``."""

    @property
    def series(self) -> DICOMSeries:
        return self._metadata

    @property
    def dataset(self) -> Any:
        """The parsed ``pydicom.Dataset`` (or dataset-like object) for this series."""
        return self._data
