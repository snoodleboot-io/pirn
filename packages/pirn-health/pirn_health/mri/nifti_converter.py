"""``NIfTIConverter`` — convert a DICOM series to NIfTI format.

Production version uses ``dcm2niix`` / ``nibabel``. Accepts a
:class:`DICOMPayload` carrying an in-memory ``pydicom.Dataset`` (the
assembler layer performs no filesystem I/O — see
``pirn_health.assemblers.dicom_pacs_assembler``). ``dcm2niix`` is an external
CLI tool that only reads from disk, so this knot — not the assembler — owns
staging the dataset to a self-cleaning temporary directory for the duration
of the subprocess call.

Algorithm:
    1. Receive payload DICOMPayload and output_nifti_path string.
    2. Validate payload is a DICOMPayload and output_nifti_path is non-empty.
    3. Write ``payload.dataset`` to a temporary directory via ``save_as``.
    4. Run dcm2niix against that temporary directory to produce the NIfTI file.
    5. Remove the temporary directory and return the output NIfTI path.

References:
    - Li et al. (2016) The first step for neuroimaging data analysis: DICOM to NIfTI conversion.
    - dcm2niix: https://github.com/rordenlab/dcm2niix
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.dicom_payload import DICOMPayload


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
            payload: DICOMPayload carrying the series metadata and parsed dataset.
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
        with tempfile.TemporaryDirectory(prefix="nifti_converter_") as staging_dir:
            await asyncio.to_thread(self._stage_dataset, payload.dataset, staging_dir)
            cmd = ["dcm2niix", "-o", output_dir, staging_dir]
            await self._run_subprocess(cmd)
        return output_nifti_path

    @staticmethod
    def _stage_dataset(dataset: Any, staging_dir: str) -> None:
        """Write ``dataset`` to a single ``.dcm`` file inside ``staging_dir``.

        ``dcm2niix`` is an external tool that only reads from disk; this is the
        one place in the DICOM pipeline that legitimately needs a real file,
        and it is scoped to a temporary directory removed by the caller.
        """
        dataset.save_as(Path(staging_dir) / "series.dcm")

    @staticmethod
    async def _run_subprocess(cmd: list[str]) -> None:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"{cmd[0]} failed: {stderr.decode()}")
