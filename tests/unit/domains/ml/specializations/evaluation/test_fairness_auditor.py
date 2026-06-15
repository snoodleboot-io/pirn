"""Tests for :class:`FairnessAuditor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.fairness_auditor import (
    FairnessAuditor,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a", "gender"), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a", "gender"), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",))


def _make_knot() -> FairnessAuditor:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        return FairnessAuditor(
            model=model,
            split=split,
            protected_attributes=("gender",),
            _config=KnotConfig(id="fair"),
        )


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_attributes(self) -> None:
        k = _make_knot()
        train = DatasetManifest(name="d:train", feature_names=("a", "gender"), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a", "gender"), row_count=20)
        model = ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",))
        split = SplitManifest(train=train, test=test)
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, protected_attributes=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_fairness_metrics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            FairnessAuditor(
                model=model,
                split=split,
                protected_attributes=("gender", "age"),
                _config=KnotConfig(id="fair"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["fair"]
        assert "gender" in out["demographic_parity"]
        assert "age" in out["equalized_odds"]
        assert isinstance(out["individual_fairness"], float)
