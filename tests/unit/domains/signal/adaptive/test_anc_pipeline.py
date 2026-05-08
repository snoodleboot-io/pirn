"""Unit tests for :class:`ANCPipeline`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.adaptive.anc_pipeline import ANCPipeline
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_REF = make_signal_payload(signal_id="test")
_ERR = make_signal_payload(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestANCPipeline(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ANCPipeline:
        return ANCPipeline(
            reference=_up("reference"),
            error=_up("error"),
            step_size=0.01,
            filter_length=32,
            _config=KnotConfig(id="anc"),
        )

    async def test_rejects_zero_step_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_REF, _ERR, step_size=0.0, filter_length=32)

    async def test_rejects_step_size_above_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_REF, _ERR, step_size=1.5, filter_length=32)

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_REF, _ERR, step_size=0.01, filter_length=0)

    async def test_rejects_mismatched_sample_rates(self) -> None:
        knot = self._make()
        diff_rate = make_signal_payload(signal_id="err", sample_rate_hz=2000.0)
        with pytest.raises(ValueError, match="sample_rate"):
            await knot.process(_REF, diff_rate, step_size=0.01, filter_length=32)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_REF, _ERR, step_size=0.01, filter_length=32)
        assert isinstance(out, SignalPayload)
        assert out.frame.sample_rate_hz == 1000.0
