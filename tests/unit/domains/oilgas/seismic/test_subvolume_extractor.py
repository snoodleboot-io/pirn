"""Unit tests for :class:`SubvolumeExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.seismic.subvolume_extractor import SubvolumeExtractor
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_negative_index(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                SubvolumeExtractor(
                    volume=volume,
                    inline_start=-1,
                    inline_end=10,
                    xline_start=0,
                    xline_end=10,
                    sample_start=0,
                    sample_end=10,
                    _config=KnotConfig(id="sv"),
                )

    def test_rejects_non_increasing_inline_range(self) -> None:
        with pytest.raises(ValueError, match="inline_end"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                SubvolumeExtractor(
                    volume=volume,
                    inline_start=10,
                    inline_end=10,
                    xline_start=0,
                    xline_end=10,
                    sample_start=0,
                    sample_end=10,
                    _config=KnotConfig(id="sv"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_sub_volume_with_dims(self) -> None:
        with Tapestry() as t:
            volume = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            SubvolumeExtractor(
                volume=volume,
                inline_start=0,
                inline_end=10,
                xline_start=0,
                xline_end=20,
                sample_start=0,
                sample_end=30,
                _config=KnotConfig(id="sv"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sv"]
        assert isinstance(out, SegyVolume)
        assert out.inline_count == 10
        assert out.xline_count == 20
        assert out.sample_count == 30
