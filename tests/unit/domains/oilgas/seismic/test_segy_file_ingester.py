"""Unit tests for :class:`SegyFileIngester`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_file_path(self) -> None:
        with pytest.raises(ValueError, match="file_path"):
            SegyFileIngester(
                file_path="",
                volume_id="vol",
                _config=KnotConfig(id="ingest"),
            )

    def test_rejects_non_string_file_path(self) -> None:
        with pytest.raises(ValueError, match="file_path"):
            SegyFileIngester(
                file_path=42,  # type: ignore[arg-type]
                volume_id="vol",
                _config=KnotConfig(id="ingest"),
            )

    def test_rejects_empty_volume_id(self) -> None:
        with pytest.raises(ValueError, match="volume_id"):
            SegyFileIngester(
                file_path="/data/x.sgy",
                volume_id="",
                _config=KnotConfig(id="ingest"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_typed_volume(self) -> None:
        with Tapestry() as t:
            SegyFileIngester(
                file_path="/data/x.sgy",
                volume_id="vol-1",
                _config=KnotConfig(id="ingest"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ingest"]
        assert isinstance(out, SegyVolume)
        assert out.volume_id == "vol-1"
