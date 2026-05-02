"""``NIfTIConverter`` — convert a DICOM series to NIfTI format.

Production version uses ``dcm2niix`` / ``nibabel``. This stub returns
an output path string derived from constructor input.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.dicom_series import DICOMSeries


class NIfTIConverter(Knot):
    """Convert a DICOM series to a NIfTI file path."""

    def __init__(
        self,
        *,
        series: DICOMSeries,
        output_nifti_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(series, DICOMSeries):
            raise TypeError("NIfTIConverter: series must be a DICOMSeries")
        if not isinstance(output_nifti_path, str) or not output_nifti_path:
            raise ValueError(
                "NIfTIConverter: output_nifti_path must be non-empty string"
            )
        self._series = series
        self._output_nifti_path = output_nifti_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_nifti_path
