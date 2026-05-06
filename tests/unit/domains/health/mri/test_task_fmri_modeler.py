"""Unit tests for :class:`TaskFMRIModeler`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.mri.task_fmri_modeler import TaskFMRIModeler
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="t")
_BOLD = {"n_volumes": 200, "n_voxels": 50000}
_EVENTS = [
    {"onset_sec": 0.0, "duration_sec": 15.0, "trial_type": "face"},
    {"onset_sec": 20.0, "duration_sec": 15.0, "trial_type": "object"},
]


def _make_knot() -> TaskFMRIModeler:
    with Tapestry():
        bd = Parameter("bd", dict, default=_BOLD, _config=KnotConfig(id="bd"))
        ev = Parameter("ev", list, default=_EVENTS, _config=KnotConfig(id="ev"))
        return TaskFMRIModeler(bold_data=bd, events=ev, tr_sec=2.0, hrf_model="spm", high_pass_hz=0.01, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_hrf_model(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "hrf_model"):
            await knot.process(bold_data=_BOLD, events=_EVENTS, tr_sec=2.0, hrf_model="gamma", high_pass_hz=0.01)

    async def test_rejects_non_positive_tr(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "tr_sec"):
            await knot.process(bold_data=_BOLD, events=_EVENTS, tr_sec=0.0, hrf_model="spm", high_pass_hz=0.01)

    async def test_rejects_non_positive_high_pass(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "high_pass_hz"):
            await knot.process(bold_data=_BOLD, events=_EVENTS, tr_sec=2.0, hrf_model="spm", high_pass_hz=0.0)

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(bold_data=_BOLD, events=_EVENTS, tr_sec=2.0, hrf_model="spm", high_pass_hz=0.01)
        assert isinstance(out, dict)
        assert "contrast_maps" in out
        assert out["n_volumes"] == 200
        assert isinstance(out["conditions"], list)
