"""Unit tests for :class:`CepstrumAnalyzer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.cepstrum_analyzer import CepstrumAnalyzer
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_invalid_kind(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="cepstrum_kind"):
                CepstrumAnalyzer(
                    signal=sig,
                    cepstrum_kind="bogus",
                    _config=KnotConfig(id="c"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CepstrumAnalyzer(signal=sig, _config=KnotConfig(id="c"))
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 1024
