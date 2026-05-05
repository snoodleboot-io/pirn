"""Unit tests for :class:`TimeSynchronizer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.time_synchronizer import TimeSynchronizer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import (
    emit_reference_frame,
    emit_signal_frame,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_max_lag_samples(self) -> None:
        with Tapestry():
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            tgt = emit_reference_frame(_config=KnotConfig(id="tgt"))
            with self.assertRaisesRegex(ValueError, "max_lag_samples"):
                TimeSynchronizer(
                    reference=ref,
                    target=tgt,
                    max_lag_samples=0,
                    _config=KnotConfig(id="ts"),
                )

    def test_rejects_negative_max_lag_samples(self) -> None:
        with Tapestry():
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            tgt = emit_reference_frame(_config=KnotConfig(id="tgt"))
            with self.assertRaisesRegex(ValueError, "max_lag_samples"):
                TimeSynchronizer(
                    reference=ref,
                    target=tgt,
                    max_lag_samples=-10,
                    _config=KnotConfig(id="ts"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            tgt = emit_reference_frame(_config=KnotConfig(id="tgt"))
            ts = TimeSynchronizer(
                reference=ref,
                target=tgt,
                max_lag_samples=256,
                _config=KnotConfig(id="ts"),
            )
        assert ts.max_lag_samples == 256


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_aligned_signal_frame(self) -> None:
        with Tapestry() as t:
            ref = emit_signal_frame(_config=KnotConfig(id="ref"))
            tgt = emit_reference_frame(_config=KnotConfig(id="tgt"))
            TimeSynchronizer(
                reference=ref,
                target=tgt,
                max_lag_samples=128,
                _config=KnotConfig(id="ts"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ts"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
