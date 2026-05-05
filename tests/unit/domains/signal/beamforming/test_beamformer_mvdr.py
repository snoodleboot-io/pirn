"""Unit tests for :class:`BeamformerMVDR`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.beamforming.beamformer_mvdr import BeamformerMVDR
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_num_elements(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "num_elements"):
                BeamformerMVDR(
                    signal=sig,
                    num_elements=0,
                    steering_angle_deg=0.0,
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_negative_diagonal_loading(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "diagonal_loading"):
                BeamformerMVDR(
                    signal=sig,
                    num_elements=4,
                    steering_angle_deg=0.0,
                    diagonal_loading=-0.1,
                    _config=KnotConfig(id="b"),
                )

    def test_accepts_zero_diagonal_loading(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BeamformerMVDR(
                signal=sig,
                num_elements=4,
                steering_angle_deg=0.0,
                diagonal_loading=0.0,
                _config=KnotConfig(id="b"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_single_channel_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BeamformerMVDR(
                signal=sig,
                num_elements=4,
                steering_angle_deg=15.0,
                diagonal_loading=0.01,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, SignalFrame)
        assert out.channel_count == 1
        assert out.signal_id == "test:mvdr"
