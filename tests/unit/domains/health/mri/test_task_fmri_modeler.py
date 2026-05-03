"""Unit tests for :class:`TaskFMRIModeler`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.task_fmri_modeler import TaskFMRIModeler
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_invalid_hrf_model(self) -> None:
        with pytest.raises(ValueError, match="hrf_model"):
            TaskFMRIModeler(
                bold_data=Parameter("bd", dict, default={}, _config=KnotConfig(id="bd")),
                events=Parameter("ev", list, default=[], _config=KnotConfig(id="ev")),
                tr_sec=2.0,
                hrf_model="gamma",
                high_pass_hz=0.01,
                _config=KnotConfig(id="t"),
            )

    def test_rejects_non_positive_tr(self) -> None:
        with pytest.raises(ValueError, match="tr_sec"):
            TaskFMRIModeler(
                bold_data=Parameter("bd", dict, default={}, _config=KnotConfig(id="bd")),
                events=Parameter("ev", list, default=[], _config=KnotConfig(id="ev")),
                tr_sec=0.0,
                hrf_model="spm",
                high_pass_hz=0.01,
                _config=KnotConfig(id="t"),
            )

    def test_rejects_non_positive_high_pass(self) -> None:
        with pytest.raises(ValueError, match="high_pass_hz"):
            TaskFMRIModeler(
                bold_data=Parameter("bd", dict, default={}, _config=KnotConfig(id="bd")),
                events=Parameter("ev", list, default=[], _config=KnotConfig(id="ev")),
                tr_sec=2.0,
                hrf_model="spm",
                high_pass_hz=0.0,
                _config=KnotConfig(id="t"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict(self) -> None:
        bold = {"n_volumes": 200, "n_voxels": 50000}
        events = [
            {"onset_sec": 0.0, "duration_sec": 15.0, "trial_type": "face"},
            {"onset_sec": 20.0, "duration_sec": 15.0, "trial_type": "object"},
        ]
        with Tapestry() as t:
            TaskFMRIModeler(
                bold_data=Parameter("bd", dict, default=bold, _config=KnotConfig(id="bd")),
                events=Parameter("ev", list, default=events, _config=KnotConfig(id="ev")),
                tr_sec=2.0,
                hrf_model="spm",
                high_pass_hz=0.01,
                _config=KnotConfig(id="t"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["t"]
        assert isinstance(out, dict)
        assert "contrast_maps" in out
        assert out["n_volumes"] == 200
        assert isinstance(out["conditions"], list)
