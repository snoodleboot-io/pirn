"""Unit tests for :class:`OnsetDetector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.onset_detector import OnsetDetector
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_hop_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="hop_length"):
                OnsetDetector(
                    signal=sig,
                    hop_length=0,
                    _config=KnotConfig(id="o"),
                )

    def test_rejects_non_positive_threshold(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="threshold"):
                OnsetDetector(
                    signal=sig,
                    hop_length=512,
                    threshold=0,
                    _config=KnotConfig(id="o"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_feature_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            OnsetDetector(
                signal=sig,
                hop_length=512,
                _config=KnotConfig(id="o"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["o"]
        assert out["feature"] == "onsets"
