"""Unit tests for :class:`EchoCanceller`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.echo_canceller import EchoCanceller
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import (
    emit_reference_frame,
    emit_signal_frame,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_filter_length(self) -> None:
        with Tapestry():
            mic = emit_signal_frame(_config=KnotConfig(id="mic"))
            far = emit_reference_frame(_config=KnotConfig(id="far"))
            with self.assertRaisesRegex(ValueError, "filter_length"):
                EchoCanceller(
                    microphone=mic,
                    far_end=far,
                    filter_length=0,
                    step_size=0.01,
                    _config=KnotConfig(id="ec"),
                )

    def test_rejects_zero_step_size(self) -> None:
        with Tapestry():
            mic = emit_signal_frame(_config=KnotConfig(id="mic"))
            far = emit_reference_frame(_config=KnotConfig(id="far"))
            with self.assertRaisesRegex(ValueError, "step_size"):
                EchoCanceller(
                    microphone=mic,
                    far_end=far,
                    filter_length=64,
                    step_size=0.0,
                    _config=KnotConfig(id="ec"),
                )

    def test_rejects_step_size_above_one(self) -> None:
        with Tapestry():
            mic = emit_signal_frame(_config=KnotConfig(id="mic"))
            far = emit_reference_frame(_config=KnotConfig(id="far"))
            with self.assertRaisesRegex(ValueError, "step_size"):
                EchoCanceller(
                    microphone=mic,
                    far_end=far,
                    filter_length=64,
                    step_size=2.0,
                    _config=KnotConfig(id="ec"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            mic = emit_signal_frame(_config=KnotConfig(id="mic"))
            far = emit_reference_frame(_config=KnotConfig(id="far"))
            ec = EchoCanceller(
                microphone=mic,
                far_end=far,
                filter_length=64,
                step_size=0.05,
                _config=KnotConfig(id="ec"),
            )
        assert ec.filter_length == 64
        assert ec.step_size == 0.05


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            mic = emit_signal_frame(_config=KnotConfig(id="mic"))
            far = emit_reference_frame(_config=KnotConfig(id="far"))
            EchoCanceller(
                microphone=mic,
                far_end=far,
                filter_length=64,
                step_size=0.05,
                _config=KnotConfig(id="ec"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ec"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
