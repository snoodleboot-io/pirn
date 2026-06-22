"""``NIfTIConverter`` — convert a DICOM series to NIfTI format.

Production version uses ``dcm2niix`` / ``nibabel``. Accepts a
:class:`DICOMPayload` so the staged filesystem path travels with the
series metadata through the transport layer.

Algorithm:
    1. Receive payload DICOMPayload and output_nifti_path string.
    2. Validate payload is a DICOMPayload and output_nifti_path is non-empty.
    3. Run dcm2niix against payload.dicom_dir to produce the NIfTI file.
    4. Return the output NIfTI path.


References:
    - Li et al. (2016) The first step for neuroimaging data analysis: DICOM to NIfTI conversion.
    - dcm2niix: https://github.com/rordenlab/dcm2niix
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.dicom_payload import DICOMPayload


async def _run_subprocess(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {stderr.decode()}")


class NIfTIConverter(Knot):
    """Convert a staged DICOM series to a NIfTI file path."""

    def __init__(
        self,
        *,
        payload: Knot | DICOMPayload,
        output_nifti_path: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            payload=payload,
            output_nifti_path=output_nifti_path,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        payload: DICOMPayload,
        output_nifti_path: str,
        **_: Any,
    ) -> str:
        """Convert the DICOM series to NIfTI format and return the output NIfTI path.

        Args:
            payload: DICOMPayload carrying the series metadata and staged directory path.
            output_nifti_path: Non-empty path for the NIfTI output file.

        Returns:
            Path string for the converted NIfTI output file.

        Raises:
            TypeError: If payload is not a DICOMPayload.
            ValueError: If output_nifti_path is empty.
        """
        if not isinstance(payload, DICOMPayload):
            raise TypeError("NIfTIConverter: payload must be a DICOMPayload")
        if not isinstance(output_nifti_path, str) or not output_nifti_path:
            raise ValueError("NIfTIConverter: output_nifti_path must be non-empty string")
        output_dir = os.path.dirname(output_nifti_path) or "."
        dicom_dir = payload.dicom_dir or "."
        cmd = ["dcm2niix", "-o", output_dir, dicom_dir]
        await _run_subprocess(cmd)
        return output_nifti_path
