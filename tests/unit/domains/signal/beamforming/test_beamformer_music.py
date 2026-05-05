"""Unit tests for :class:`BeamformerMUSIC`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.beamforming.beamformer_music import BeamformerMUSIC
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_num_elements(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "num_elements"):
                BeamformerMUSIC(
                    signal=sig,
                    num_elements=0,
                    num_sources=1,
                    angle_scan_deg=(-90.0, 90.0, 1.0),
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_non_positive_num_sources(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "num_sources"):
                BeamformerMUSIC(
                    signal=sig,
                    num_elements=4,
                    num_sources=0,
                    angle_scan_deg=(-90.0, 90.0, 1.0),
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_zero_step(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "non-zero"):
                BeamformerMUSIC(
                    signal=sig,
                    num_elements=4,
                    num_sources=1,
                    angle_scan_deg=(-90.0, 90.0, 0.0),
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_invalid_angle_scan_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "angle_scan_deg"):
                BeamformerMUSIC(
                    signal=sig,
                    num_elements=4,
                    num_sources=1,
                    angle_scan_deg=(-90.0, 90.0),  # type: ignore[arg-type]
                    _config=KnotConfig(id="b"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BeamformerMUSIC(
                signal=sig,
                num_elements=4,
                num_sources=2,
                angle_scan_deg=(-90.0, 90.0, 1.0),
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 180
