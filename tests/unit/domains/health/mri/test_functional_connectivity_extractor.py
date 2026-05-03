"""Unit tests for :class:`FunctionalConnectivityExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.functional_connectivity_extractor import FunctionalConnectivityExtractor
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_atlas(self) -> None:
        with pytest.raises(ValueError, match="atlas"):
            FunctionalConnectivityExtractor(
                bold_timeseries=Parameter("bt", dict, default={}, _config=KnotConfig(id="bt")),
                atlas="",
                connectivity_measure="correlation",
                confound_strategy="none",
                _config=KnotConfig(id="f"),
            )

    def test_rejects_invalid_measure(self) -> None:
        with pytest.raises(ValueError, match="connectivity_measure"):
            FunctionalConnectivityExtractor(
                bold_timeseries=Parameter("bt", dict, default={}, _config=KnotConfig(id="bt")),
                atlas="schaefer200",
                connectivity_measure="covariance",
                confound_strategy="none",
                _config=KnotConfig(id="f"),
            )

    def test_rejects_invalid_confound_strategy(self) -> None:
        with pytest.raises(ValueError, match="confound_strategy"):
            FunctionalConnectivityExtractor(
                bold_timeseries=Parameter("bt", dict, default={}, _config=KnotConfig(id="bt")),
                atlas="schaefer200",
                connectivity_measure="correlation",
                confound_strategy="aroma",
                _config=KnotConfig(id="f"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict(self) -> None:
        ts_data = {
            "roi_timeseries": {"ROI_1": [1.0, 2.0], "ROI_2": [3.0, 4.0]},
            "n_timepoints": 2,
            "tr_sec": 2.0,
        }
        with Tapestry() as t:
            FunctionalConnectivityExtractor(
                bold_timeseries=Parameter("bt", dict, default=ts_data, _config=KnotConfig(id="bt")),
                atlas="schaefer200",
                connectivity_measure="correlation",
                confound_strategy="none",
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, dict)
        assert "connectivity_matrix" in out
        assert out["n_rois"] == 2
        assert out["measure"] == "correlation"
