"""Unit tests for :class:`NIfTIConverter`."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.nifti_converter import NIfTIConverter
from pirn.domains.health.types.dicom_payload import DICOMPayload
from pirn.domains.health.types.dicom_series import DICOMSeries

_CFG = KnotConfig(id="c")
_PAYLOAD = DICOMPayload(series=DICOMSeries(), dicom_dir="/tmp/dicom")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> NIfTIConverter:
        return NIfTIConverter(payload=_PAYLOAD, output_nifti_path="out.nii.gz", _config=_CFG)

    async def test_rejects_non_payload(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DICOMPayload"):
            await knot.process(payload="x", output_nifti_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(payload=_PAYLOAD, output_nifti_path="")

    async def test_returns_nifti_path(self) -> None:
        knot = self._make_knot()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            out = await knot.process(payload=_PAYLOAD, output_nifti_path="out.nii.gz")
        assert out == "out.nii.gz"
