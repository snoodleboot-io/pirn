"""Unit tests for :class:`StackProcessor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.seismic.stack_processor import StackProcessor
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_requires_gather_kwarg(self) -> None:
        with pytest.raises(TypeError, match="gather"):
            StackProcessor(_config=KnotConfig(id="st"))  # type: ignore[call-arg]


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_stacked_volume(self) -> None:
        with Tapestry() as t:
            gather = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            StackProcessor(gather=gather, _config=KnotConfig(id="st"))
        result = await t.run(RunRequest())
        out = result.outputs["st"]
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":stacked")
