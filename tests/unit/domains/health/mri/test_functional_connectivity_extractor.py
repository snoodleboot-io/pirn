"""Unit tests for :class:`FunctionalConnectivityExtractor`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.mri.functional_connectivity_extractor import FunctionalConnectivityExtractor
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="f")
_TS_DATA = {
    "roi_timeseries": {"ROI_1": [1.0, 2.0], "ROI_2": [3.0, 4.0]},
    "n_timepoints": 2,
    "tr_sec": 2.0,
}


def _make_knot() -> FunctionalConnectivityExtractor:
    with Tapestry():
        src = Parameter("bt", dict, default=_TS_DATA, _config=KnotConfig(id="bt"))
        return FunctionalConnectivityExtractor(
            bold_timeseries=src,
            atlas="schaefer200",
            connectivity_measure="correlation",
            confound_strategy="none",
            _config=_CFG,
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_atlas(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "atlas"):
            await knot.process(bold_timeseries=_TS_DATA, atlas="", connectivity_measure="correlation", confound_strategy="none")

    async def test_rejects_invalid_measure(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "connectivity_measure"):
            await knot.process(bold_timeseries=_TS_DATA, atlas="schaefer200", connectivity_measure="covariance", confound_strategy="none")

    async def test_rejects_invalid_confound_strategy(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "confound_strategy"):
            await knot.process(bold_timeseries=_TS_DATA, atlas="schaefer200", connectivity_measure="correlation", confound_strategy="aroma")

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(bold_timeseries=_TS_DATA, atlas="schaefer200", connectivity_measure="correlation", confound_strategy="none")
        assert isinstance(out, dict)
        assert "connectivity_matrix" in out
        assert out["n_rois"] == 2
        assert out["measure"] == "correlation"
