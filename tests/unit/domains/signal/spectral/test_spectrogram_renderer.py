"""Unit tests for :class:`SpectrogramRenderer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.spectrogram_renderer import SpectrogramRenderer
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_window_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                SpectrogramRenderer(
                    signal=sig,
                    window_length=0,
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_invalid_scaling(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="scaling"):
                SpectrogramRenderer(
                    signal=sig,
                    window_length=64,
                    scaling="bad",
                    _config=KnotConfig(id="r"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SpectrogramRenderer(
                signal=sig,
                window_length=128,
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 65
