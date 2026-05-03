"""Unit tests for :class:`SleepStageClassifier`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.sleep_stage_classifier import SleepStageClassifier
from pirn.tapestry import Tapestry


@knot
async def emit_psg_data() -> dict[str, Any]:
    return {
        "epochs": [
            {"channel_data": {"EEG": [0.1, 0.2], "EOG": [0.0], "EMG": [0.05]}},
            {"channel_data": {"EEG": [0.3, 0.4], "EOG": [0.1], "EMG": [0.02]}},
        ],
        "sample_rate_hz": 256.0,
    }


class TestConstruction:
    def test_rejects_non_knot_psg_data(self) -> None:
        with pytest.raises(TypeError, match="psg_data"):
            SleepStageClassifier(
                psg_data="not-a-knot",  # type: ignore[arg-type]
                epoch_duration_sec=30,
                _config=KnotConfig(id="sc"),
            )

    def test_rejects_non_30_epoch_duration(self) -> None:
        with Tapestry():
            p = emit_psg_data(_config=KnotConfig(id="p"))
            with pytest.raises(ValueError, match="epoch_duration_sec"):
                SleepStageClassifier(
                    psg_data=p,
                    epoch_duration_sec=20,
                    _config=KnotConfig(id="sc"),
                )

    def test_rejects_empty_channels(self) -> None:
        with Tapestry():
            p = emit_psg_data(_config=KnotConfig(id="p"))
            with pytest.raises(ValueError, match="channels"):
                SleepStageClassifier(
                    psg_data=p,
                    epoch_duration_sec=30,
                    channels=(),
                    _config=KnotConfig(id="sc"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict_with_required_keys(self) -> None:
        with Tapestry() as t:
            p = emit_psg_data(_config=KnotConfig(id="p"))
            SleepStageClassifier(
                psg_data=p,
                epoch_duration_sec=30,
                _config=KnotConfig(id="sc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sc"]
        assert isinstance(out, dict)
        assert "stage_labels" in out
        assert "total_epochs" in out
        assert "sleep_efficiency_pct" in out

    async def test_stage_labels_count_matches_epochs(self) -> None:
        with Tapestry() as t:
            p = emit_psg_data(_config=KnotConfig(id="p"))
            SleepStageClassifier(
                psg_data=p,
                epoch_duration_sec=30,
                _config=KnotConfig(id="sc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sc"]
        assert out["total_epochs"] == 2
        assert len(out["stage_labels"]) == 2
        valid_stages = {"W", "N1", "N2", "N3", "REM"}
        for label in out["stage_labels"]:
            assert label in valid_stages
