"""Unit tests for :class:`NLMSAdaptiveFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.adaptive.nlms_adaptive_filter import NLMSAdaptiveFilter
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
                NLMSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=0,
                    step_size=0.01,
                    _config=KnotConfig(id="nlms"),
                )

    def test_rejects_non_positive_step_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with self.assertRaisesRegex(ValueError, "step_size"):
                NLMSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=8,
                    step_size=0,
                    _config=KnotConfig(id="nlms"),
                )

    def test_rejects_negative_regularization(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            with self.assertRaisesRegex(ValueError, "regularization"):
                NLMSAdaptiveFilter(
                    signal=sig,
                    reference=ref,
                    filter_length=8,
                    step_size=0.01,
                    regularization=-1.0,
                    _config=KnotConfig(id="nlms"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ref = emit_reference_frame(_config=KnotConfig(id="ref"))
            NLMSAdaptiveFilter(
                signal=sig,
                reference=ref,
                filter_length=8,
                step_size=0.01,
                _config=KnotConfig(id="nlms"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["nlms"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:nlms"
