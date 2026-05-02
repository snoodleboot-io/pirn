"""Unit tests for :class:`DICOMIngestor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.dicom_ingestor import DICOMIngestor
from pirn.domains.health.types.dicom_series import DICOMSeries
from pirn.tapestry import Tapestry
from tests.unit.domains.health.conftest import StubPACSClient


class TestConstruction:
    def test_rejects_non_client(self) -> None:
        with pytest.raises(TypeError, match="PACSClient"):
            DICOMIngestor(
                client="x",  # type: ignore[arg-type]
                study_uid="s",
                series_uid="r",
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_string_uid(self) -> None:
        with pytest.raises(TypeError, match="study_uid"):
            DICOMIngestor(
                client=StubPACSClient(),
                study_uid=42,  # type: ignore[arg-type]
                series_uid="r",
                _config=KnotConfig(id="i"),
            )

    def test_rejects_empty_uid(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            DICOMIngestor(
                client=StubPACSClient(),
                study_uid="",
                series_uid="r",
                _config=KnotConfig(id="i"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dicom_series(self) -> None:
        with Tapestry() as t:
            DICOMIngestor(
                client=StubPACSClient(),
                study_uid="ST",
                series_uid="SE",
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, DICOMSeries)
        assert out.study_uid == "ST"
