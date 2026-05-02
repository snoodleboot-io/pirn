"""Unit tests for :class:`SegyHeaderParser`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.seismic.segy_header_parser import SegyHeaderParser
from pirn.domains.oilgas.types.parsed_trace_header import ParsedTraceHeader
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_requires_volume_kwarg(self) -> None:
        with pytest.raises(TypeError, match="volume"):
            SegyHeaderParser(_config=KnotConfig(id="hp"))  # type: ignore[call-arg]


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_parsed_header(self) -> None:
        with Tapestry() as t:
            volume = SegyFileIngester(
                file_path="/d/x.sgy",
                volume_id="v",
                _config=KnotConfig(id="ingest"),
            )
            SegyHeaderParser(volume=volume, _config=KnotConfig(id="hp"))
        result = await t.run(RunRequest())
        assert isinstance(result.outputs["hp"], ParsedTraceHeader)
