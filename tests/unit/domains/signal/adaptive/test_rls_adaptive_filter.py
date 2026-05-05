"""Unit tests for :class:`RLSAdaptiveFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.rls_adaptive_filter import RLSAdaptiveFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import (
    emit_reference_frame,
    emit_signal_frame,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_filter_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with self.assertRaisesRegex(ValueError, "filter_length"):
                RLSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=0,
                    forgetting_factor=0.99,
                    _config=KnotConfig(id="rls"),
                )

    def test_rejects_forgetting_factor_le_zero(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with self.assertRaisesRegex(ValueError, "forgetting_factor"):
                RLSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=8,
                    forgetting_factor=0.0,
                    _config=KnotConfig(id="rls"),
                )

    def test_rejects_forgetting_factor_gt_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with self.assertRaisesRegex(ValueError, "forgetting_factor"):
                RLSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=8,
                    forgetting_factor=1.5,
                    _config=KnotConfig(id="rls"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            RLSAdaptiveFilter(
                signal=sig,
                reference=ref,
                filter_length=8,
                forgetting_factor=0.99,
                _config=KnotConfig(id="rls"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rls"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:rls"
