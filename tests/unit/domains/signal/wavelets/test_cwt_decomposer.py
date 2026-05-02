"""Unit tests for :class:`CWTDecomposer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.cwt_decomposer import CWTDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_empty_wavelet_name(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="non-empty"):
                CWTDecomposer(
                    signal=sig,
                    wavelet_name="",
                    scale_count=8,
                    _config=KnotConfig(id="w"),
                )

    def test_rejects_non_positive_scale_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="scale_count"):
                CWTDecomposer(
                    signal=sig,
                    wavelet_name="morl",
                    scale_count=0,
                    _config=KnotConfig(id="w"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_wavelet_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CWTDecomposer(
                signal=sig,
                wavelet_name="morl",
                scale_count=16,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletFrame)
        assert out.wavelet_name == "morl"
        assert out.scale_count == 16
