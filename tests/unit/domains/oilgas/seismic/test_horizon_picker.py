"""Unit tests for :class:`HorizonPicker`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.horizon_picker import HorizonPicker
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_horizon_name(self) -> None:
        with pytest.raises(ValueError, match="horizon_name"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                HorizonPicker(
                    volume=volume,
                    horizon_name="",
                    seed_inline=0,
                    seed_xline=0,
                    _config=KnotConfig(id="hp"),
                )

    def test_rejects_negative_seed(self) -> None:
        with pytest.raises(ValueError, match="seed_inline"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                HorizonPicker(
                    volume=volume,
                    horizon_name="top_a",
                    seed_inline=-1,
                    seed_xline=0,
                    _config=KnotConfig(id="hp"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_horizon_volume(self) -> None:
        with Tapestry() as t:
            volume = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            HorizonPicker(
                volume=volume,
                horizon_name="niobrara",
                seed_inline=10,
                seed_xline=20,
                _config=KnotConfig(id="hp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["hp"]
        assert isinstance(out, SegyVolume)
        assert "horizon_niobrara" in out.volume_id
