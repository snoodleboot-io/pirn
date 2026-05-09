"""Unit tests for :class:`DICOMIngestor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.dicom_ingestor import DICOMIngestor
from pirn.domains.health.types.dicom_payload import DICOMPayload
from tests.unit.domains.health.conftest import StubPACSClient

_CFG = KnotConfig(id="i")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DICOMIngestor:
        return DICOMIngestor(
            client=StubPACSClient(),
            study_uid="ST",
            series_uid="SE",
            staging_dir="/tmp/dicom",
            _config=_CFG,
        )

    async def test_rejects_non_client(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "PACSClient"):
            await knot.process(client="x", study_uid="s", series_uid="r", staging_dir="/tmp")  # type: ignore[arg-type]

    async def test_rejects_non_string_uid(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "study_uid"):
            await knot.process(client=StubPACSClient(), study_uid=42, series_uid="r", staging_dir="/tmp")  # type: ignore[arg-type]

    async def test_rejects_empty_uid(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(client=StubPACSClient(), study_uid="", series_uid="r", staging_dir="/tmp")

    async def test_rejects_empty_staging_dir(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(client=StubPACSClient(), study_uid="ST", series_uid="SE", staging_dir="")

    async def test_returns_dicom_payload(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            client=StubPACSClient(), study_uid="ST", series_uid="SE", staging_dir="/tmp/dicom"
        )
        assert isinstance(out, DICOMPayload)
        assert out.series.study_uid == "ST"
        assert out.dicom_dir == "/tmp/dicom"
