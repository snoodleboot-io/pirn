"""Tests for :class:`FeatureSelector` — each documented method really scores the features."""

from __future__ import annotations

import unittest

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_ml.features.feature_selector import FeatureSelector
from pirn_ml.types.data_split_payload import DataSplitPayload
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_arrays import SplitArrays
from pirn_ml.types.split_manifest import SplitManifest

pytest.importorskip("sklearn")


class _Fixtures:
    names: tuple[str, ...] = ("a", "b", "c", "d")

    @staticmethod
    def split(
        x_train: np.ndarray,
        y_train: np.ndarray | None,
        x_test: np.ndarray | None = None,
    ) -> DataSplitPayload:
        test = x_train[:10] if x_test is None else x_test
        return DataSplitPayload(
            metadata=SplitManifest(
                train=DatasetManifest(
                    name="d:train",
                    feature_names=_Fixtures.names,
                    target_name="y",
                    row_count=len(x_train),
                ),
                test=DatasetManifest(
                    name="d:test",
                    feature_names=_Fixtures.names,
                    target_name="y",
                    row_count=len(test),
                ),
            ),
            data=SplitArrays(
                X_train=x_train,
                X_test=test,
                y_train=y_train,
                y_test=None if y_train is None else y_train[: len(test)],
            ),
        )

    @staticmethod
    def knot() -> FeatureSelector:
        selector = FeatureSelector.__new__(FeatureSelector)
        object.__setattr__(selector, "_config", KnotConfig(id="x"))
        return selector


class TestVariance(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_the_highest_variance_columns(self) -> None:
        rng = np.random.default_rng(0)
        x = np.column_stack(
            [
                rng.normal(0, 0.1, 200),
                rng.normal(0, 5.0, 200),
                np.full(200, 3.0),
                rng.normal(0, 2.0, 200),
            ]
        )
        out = await _Fixtures.knot().process(split=_Fixtures.split(x, None), k=2, method="variance")
        assert out.metadata.train.feature_names == ("b", "d")
        assert out.metadata.test.feature_names == ("b", "d")
        np.testing.assert_array_equal(out.data.X_train, x[:, [1, 3]])
        np.testing.assert_array_equal(out.data.X_test, x[:10, [1, 3]])

    async def test_scores_on_train_only(self) -> None:
        rng = np.random.default_rng(1)
        x_train = np.column_stack(
            [
                rng.normal(0, 9.0, 50),
                rng.normal(0, 0.1, 50),
                rng.normal(0, 0.1, 50),
                rng.normal(0, 0.1, 50),
            ]
        )
        x_test = np.column_stack(
            [
                rng.normal(0, 0.1, 20),
                rng.normal(0, 0.1, 20),
                rng.normal(0, 0.1, 20),
                rng.normal(0, 9.0, 20),
            ]
        )
        out = await _Fixtures.knot().process(
            split=_Fixtures.split(x_train, None, x_test), k=1, method="variance"
        )
        assert out.metadata.train.feature_names == ("a",)


class TestMutualInformation(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_the_feature_that_determines_a_discrete_label(self) -> None:
        rng = np.random.default_rng(2)
        x = rng.normal(0, 1, (300, 4))
        y = (x[:, 2] > 0).astype(int)
        out = await _Fixtures.knot().process(
            split=_Fixtures.split(x, y), k=1, method="mutual_information"
        )
        assert out.metadata.train.feature_names == ("c",)

    async def test_keeps_the_feature_that_drives_a_continuous_target(self) -> None:
        rng = np.random.default_rng(3)
        x = rng.normal(0, 1, (300, 4))
        y = 2.5 * x[:, 0] + rng.normal(0, 0.05, 300)
        out = await _Fixtures.knot().process(
            split=_Fixtures.split(x, y), k=1, method="mutual_information"
        )
        assert out.metadata.train.feature_names == ("a",)


class TestRecursiveFeatureElimination(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_the_features_the_label_depends_on(self) -> None:
        rng = np.random.default_rng(4)
        x = rng.normal(0, 1, (400, 4))
        y = (3.0 * x[:, 1] - 3.0 * x[:, 3] > 0).astype(int)
        out = await _Fixtures.knot().process(split=_Fixtures.split(x, y), k=2, method="rfe")
        assert out.metadata.train.feature_names == ("b", "d")

    async def test_keeps_the_features_a_continuous_target_depends_on(self) -> None:
        rng = np.random.default_rng(5)
        x = rng.normal(0, 1, (200, 4))
        y = 4.0 * x[:, 0] + 2.0 * x[:, 2] + rng.normal(0, 0.01, 200)
        out = await _Fixtures.knot().process(split=_Fixtures.split(x, y), k=2, method="rfe")
        assert out.metadata.train.feature_names == ("a", "c")


@KnotFactory.knot
async def emit_split_with_one_wide_column() -> DataSplitPayload:
    rng = np.random.default_rng(6)
    x = np.column_stack(
        [rng.normal(0, 1, 60), rng.normal(0, 10, 60), rng.normal(0, 1, 60), rng.normal(0, 1, 60)]
    )
    return _Fixtures.split(x, None)


class TestFeatureSelectorInATapestry(unittest.IsolatedAsyncioTestCase):
    async def test_runs_as_a_knot(self) -> None:
        with Tapestry() as t:
            split = emit_split_with_one_wide_column(_config=KnotConfig(id="split"))
            FeatureSelector(split=split, k=1, method="variance", _config=KnotConfig(id="sel"))
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["sel"].metadata.train.feature_names == ("b",)


class TestFeatureSelectorValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_method(self) -> None:
        with pytest.raises(ValueError, match="method must be"):
            await _Fixtures.knot().process(
                split=_Fixtures.split(np.zeros((20, 4)), None), k=2, method="bogus"
            )

    async def test_rejects_k_above_feature_count(self) -> None:
        with pytest.raises(ValueError, match="exceeds the 4 features"):
            await _Fixtures.knot().process(
                split=_Fixtures.split(np.zeros((20, 4)), None), k=5, method="variance"
            )

    async def test_target_based_method_requires_y_train(self) -> None:
        with pytest.raises(ValueError, match="requires y_train"):
            await _Fixtures.knot().process(
                split=_Fixtures.split(np.zeros((20, 4)), None), k=2, method="rfe"
            )

    async def test_rejects_arrays_that_disagree_with_feature_names(self) -> None:
        with pytest.raises(ValueError, match="4 columns"):
            await _Fixtures.knot().process(
                split=_Fixtures.split(np.zeros((20, 3)), None), k=2, method="variance"
            )

    async def test_rejects_manifest_only_split(self) -> None:
        manifest = _Fixtures.split(np.zeros((20, 4)), None).metadata
        with pytest.raises(TypeError, match="DataSplitPayload"):
            await _Fixtures.knot().process(split=manifest, k=2, method="variance")
