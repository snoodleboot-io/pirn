"""Unit tests for :class:`MultiresolutionAnalyzer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.multiresolution_analyzer import (
    MultiresolutionAnalyzer,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_empty_wavelet_name(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="non-empty"):
                MultiresolutionAnalyzer(
                    signal=sig,
                    wavelet_name="",
                    level_count=3,
                    _config=KnotConfig(id="w"),
                )

    def test_rejects_non_positive_level_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="level_count"):
                MultiresolutionAnalyzer(
                    signal=sig,
                    wavelet_name="db4",
                    level_count=0,
                    _config=KnotConfig(id="w"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_wavelet_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MultiresolutionAnalyzer(
                signal=sig,
                wavelet_name="sym4",
                level_count=3,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletFrame)
        assert out.wavelet_name == "sym4"
        assert out.scale_count == 3
