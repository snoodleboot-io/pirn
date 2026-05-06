"""Unit tests for :class:`SleepStageClassifier`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.health.eeg_meg.sleep_stage_classifier import SleepStageClassifier
from pirn.tapestry import Tapestry

_PSG_DATA: dict[str, Any] = {
    "epochs": [
        {"channel_data": {"EEG": [0.1, 0.2], "EOG": [0.0], "EMG": [0.05]}},
        {"channel_data": {"EEG": [0.3, 0.4], "EOG": [0.1], "EMG": [0.02]}},
    ],
    "sample_rate_hz": 256.0,
}


@knot
async def emit_psg_data() -> dict[str, Any]:
    return _PSG_DATA


def _make_knot() -> SleepStageClassifier:
    with Tapestry():
        p = emit_psg_data(_config=KnotConfig(id="p"))
        return SleepStageClassifier(
            psg_data=p,
            epoch_duration_sec=30,
            _config=KnotConfig(id="sc"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_psg_data(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(TypeError, "dict"):
            await knot_inst.process(psg_data="not-a-dict", epoch_duration_sec=30)  # type: ignore[arg-type]

    async def test_rejects_non_30_epoch_duration(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "epoch_duration_sec"):
            await knot_inst.process(psg_data=_PSG_DATA, epoch_duration_sec=20)

    async def test_rejects_empty_channels(self) -> None:
        knot_inst = _make_knot()
        with self.assertRaisesRegex(ValueError, "channels"):
            await knot_inst.process(psg_data=_PSG_DATA, epoch_duration_sec=30, channels=())

    async def test_returns_dict_with_required_keys(self) -> None:
        knot_inst = _make_knot()
        out = await knot_inst.process(psg_data=_PSG_DATA, epoch_duration_sec=30)
        assert isinstance(out, dict)
        assert "stage_labels" in out
        assert "total_epochs" in out
        assert "sleep_efficiency_pct" in out

    async def test_stage_labels_count_matches_epochs(self) -> None:
        knot_inst = _make_knot()
        out = await knot_inst.process(psg_data=_PSG_DATA, epoch_duration_sec=30)
        assert out["total_epochs"] == 2
        assert len(out["stage_labels"]) == 2
        valid_stages = {"W", "N1", "N2", "N3", "REM"}
        for label in out["stage_labels"]:
            assert label in valid_stages
