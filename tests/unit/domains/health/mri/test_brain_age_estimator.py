"""Unit tests for :class:`BrainAgeEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.mri.brain_age_estimator import BrainAgeEstimator
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_model_name(self) -> None:
        with pytest.raises(ValueError, match="model_name"):
            BrainAgeEstimator(
                mri_features=Parameter("mf", dict, default={}, _config=KnotConfig(id="mf")),
                model_name="",
                reference_population="ukbiobank",
                _config=KnotConfig(id="b"),
            )

    def test_rejects_invalid_population(self) -> None:
        with pytest.raises(ValueError, match="reference_population"):
            BrainAgeEstimator(
                mri_features=Parameter("mf", dict, default={}, _config=KnotConfig(id="mf")),
                model_name="brain_age_v1",
                reference_population="hcp",
                _config=KnotConfig(id="b"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict(self) -> None:
        features = {
            "cortical_thickness": {"lh_frontal": 2.5},
            "subcortical_volumes": {"hippocampus": 3500.0},
            "chronological_age": 45.0,
        }
        with Tapestry() as t:
            BrainAgeEstimator(
                mri_features=Parameter("mf", dict, default=features, _config=KnotConfig(id="mf")),
                model_name="brain_age_v1",
                reference_population="ukbiobank",
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, dict)
        assert "predicted_brain_age" in out
        assert "brain_age_gap" in out
        assert "confidence_interval" in out
