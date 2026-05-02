"""Unit tests for :class:`StaticCorrection`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.seismic.static_correction import StaticCorrection
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_numeric_datum(self) -> None:
        with pytest.raises(TypeError, match="datum_elevation_m"):
            with Tapestry():
                gather = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                StaticCorrection(
                    gather=gather,
                    datum_elevation_m="hi",  # type: ignore[arg-type]
                    replacement_velocity_m_s=2000.0,
                    _config=KnotConfig(id="sc"),
                )

    def test_rejects_non_positive_velocity(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            with Tapestry():
                gather = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                StaticCorrection(
                    gather=gather,
                    datum_elevation_m=100.0,
                    replacement_velocity_m_s=0.0,
                    _config=KnotConfig(id="sc"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_corrected_volume(self) -> None:
        with Tapestry() as t:
            gather = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            StaticCorrection(
                gather=gather,
                datum_elevation_m=200.0,
                replacement_velocity_m_s=1800.0,
                _config=KnotConfig(id="sc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sc"]
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":static")
