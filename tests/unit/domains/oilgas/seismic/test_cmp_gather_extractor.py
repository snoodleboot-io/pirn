"""Unit tests for :class:`CmpGatherExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.cmp_gather_extractor import CmpGatherExtractor
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_negative_inline(self) -> None:
        with pytest.raises(ValueError, match="cmp_inline"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                CmpGatherExtractor(
                    volume=volume,
                    cmp_inline=-1,
                    cmp_xline=0,
                    _config=KnotConfig(id="cmp"),
                )

    def test_rejects_non_int_xline(self) -> None:
        with pytest.raises(ValueError, match="cmp_xline"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                CmpGatherExtractor(
                    volume=volume,
                    cmp_inline=0,
                    cmp_xline=1.5,  # type: ignore[arg-type]
                    _config=KnotConfig(id="cmp"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_subvolume(self) -> None:
        with Tapestry() as t:
            volume = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            CmpGatherExtractor(
                volume=volume,
                cmp_inline=10,
                cmp_xline=20,
                _config=KnotConfig(id="cmp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cmp"]
        assert isinstance(out, SegyVolume)
        assert "cmp_10_20" in out.volume_id
