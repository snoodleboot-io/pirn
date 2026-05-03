"""Unit tests for :class:`SampleEntropyCalculator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.sample_entropy_calculator import SampleEntropyCalculator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_m(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match=r"\bm\b"):
                SampleEntropyCalculator(
                    signal=sig,
                    m=0,
                    r=0.2,
                    _config=KnotConfig(id="se"),
                )

    def test_rejects_non_positive_r(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match=r"\br\b"):
                SampleEntropyCalculator(
                    signal=sig,
                    m=2,
                    r=0.0,
                    _config=KnotConfig(id="se"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            se = SampleEntropyCalculator(
                signal=sig,
                m=2,
                r=0.2,
                _config=KnotConfig(id="se"),
            )
        assert se.m == 2
        assert se.r == 0.2


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_entropy_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SampleEntropyCalculator(
                signal=sig,
                m=2,
                r=0.2,
                _config=KnotConfig(id="se"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["se"]
        assert isinstance(out, dict)
        assert "sample_entropy" in out
        assert "m" in out
        assert "r" in out
