"""Unit tests for :class:`BrainAgeEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_health.mri.brain_age_estimator import BrainAgeEstimator

_CFG = KnotConfig(id="b")
_FEATURES = {
    "cortical_thickness": {"lh_frontal": 2.5},
    "subcortical_volumes": {"hippocampus": 3500.0},
    "chronological_age": 45.0,
}


def _make_knot() -> BrainAgeEstimator:
    with Tapestry():
        src = Parameter("mf", dict, default=_FEATURES, _config=KnotConfig(id="mf"))
        return BrainAgeEstimator(mri_features=src, model_name="brain_age_v1", reference_population="ukbiobank", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_model_name(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "model_name"):
            await knot.process(mri_features=_FEATURES, model_name="", reference_population="ukbiobank")

    async def test_rejects_invalid_population(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "reference_population"):
            await knot.process(mri_features=_FEATURES, model_name="v1", reference_population="hcp")

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(mri_features=_FEATURES, model_name="brain_age_v1", reference_population="ukbiobank")
        assert isinstance(out, dict)
        assert "predicted_brain_age" in out
        assert "brain_age_gap" in out
        assert "confidence_interval" in out
