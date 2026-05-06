"""Unit tests for :class:`DICOMIngestor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.mri.dicom_ingestor import DICOMIngestor
from pirn.domains.health.types.dicom_series import DICOMSeries
from tests.unit.domains.health.conftest import StubPACSClient

_CFG = KnotConfig(id="i")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DICOMIngestor:
        return DICOMIngestor(client=StubPACSClient(), study_uid="ST", series_uid="SE", _config=_CFG)

    async def test_rejects_non_client(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "PACSClient"):
            await knot.process(client="x", study_uid="s", series_uid="r")  # type: ignore[arg-type]

    async def test_rejects_non_string_uid(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "study_uid"):
            await knot.process(client=StubPACSClient(), study_uid=42, series_uid="r")  # type: ignore[arg-type]

    async def test_rejects_empty_uid(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(client=StubPACSClient(), study_uid="", series_uid="r")

    async def test_returns_dicom_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(client=StubPACSClient(), study_uid="ST", series_uid="SE")
        assert isinstance(out, DICOMSeries)
        assert out.study_uid == "ST"
