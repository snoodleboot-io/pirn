"""``NIfTIConverter`` — convert a DICOM series to NIfTI format.

Production version uses ``dcm2niix`` / ``nibabel``. This stub returns
an output path string derived from constructor input.

Algorithm:
    1. Receive series DICOMSeries and output_nifti_path string.
    2. Validate series is a DICOMSeries and output_nifti_path is non-empty.
    3. Convert DICOM pixel data to NIfTI voxel array and write header.
    4. Write the resulting NIfTI file to output_nifti_path.
    5. Return the output NIfTI path.


References:
    - Li et al. (2016) The first step for neuroimaging data analysis: DICOM to NIfTI conversion.
    - dcm2niix: https://github.com/rordenlab/dcm2niix
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
        series: Knot | DICOMSeries,
        output_nifti_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            series=series,
            output_nifti_path=output_nifti_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        series: DICOMSeries,
        output_nifti_path: str,
        **_: Any,
    ) -> str:
        """Convert the DICOM series to NIfTI format and return the output NIfTI path.

        Args:
            series: DICOMSeries carrying the DICOM data to convert.
            output_nifti_path: Non-empty path for the NIfTI output file.

        Returns:
            Path string for the converted NIfTI output file.

        Raises:
            TypeError: If series is not a DICOMSeries.
            ValueError: If output_nifti_path is empty.
        """
        if not isinstance(series, DICOMSeries):
            raise TypeError("NIfTIConverter: series must be a DICOMSeries")
        if not isinstance(output_nifti_path, str) or not output_nifti_path:
            raise ValueError("NIfTIConverter: output_nifti_path must be non-empty string")
        return output_nifti_path
