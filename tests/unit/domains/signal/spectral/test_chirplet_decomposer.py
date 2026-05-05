"""Unit tests for :class:`ChirpletDecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.chirplet_decomposer import ChirpletDecomposer
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_chirplet_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive integer"):
                ChirpletDecomposer(
                    signal=sig,
                    chirplet_count=0,
                    _config=KnotConfig(id="c"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ChirpletDecomposer(
                signal=sig,
                chirplet_count=8,
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 8
