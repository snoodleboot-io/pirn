"""Unit tests for :class:`WalkForwardValidator`."""

from __future__ import annotations

import unittest

from pirn.domains.ml.specializations.evaluation.walk_forward_validator import (
    WalkForwardValidator,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest


def _dataset(row_count: int = 50) -> DatasetManifest:
    return DatasetManifest(
        name="test-dataset",
        feature_names=("a", "b"),
        target_name="y",
        row_count=row_count,
    )


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_time_column(self) -> None:
        validator = WalkForwardValidator.__new__(WalkForwardValidator)
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=_dataset(),
                time_column="",
                train_window=10,
                test_window=5,
                algorithm="arima",
                n_steps=5,
            )

    async def test_rejects_train_window_less_than_1(self) -> None:
        validator = WalkForwardValidator.__new__(WalkForwardValidator)
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=_dataset(),
                time_column="ts",
                train_window=0,
                test_window=5,
                algorithm="arima",
                n_steps=5,
            )

    async def test_rejects_test_window_less_than_1(self) -> None:
        validator = WalkForwardValidator.__new__(WalkForwardValidator)
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=_dataset(),
                time_column="ts",
                train_window=10,
                test_window=0,
                algorithm="arima",
                n_steps=5,
            )

    async def test_rejects_empty_algorithm(self) -> None:
        validator = WalkForwardValidator.__new__(WalkForwardValidator)
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=_dataset(),
                time_column="ts",
                train_window=10,
                test_window=5,
                algorithm="",
                n_steps=5,
            )

    async def test_rejects_n_steps_less_than_1(self) -> None:
        validator = WalkForwardValidator.__new__(WalkForwardValidator)
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=_dataset(),
                time_column="ts",
                train_window=10,
                test_window=5,
                algorithm="arima",
                n_steps=0,
            )

    async def test_rejects_dataset_too_small(self) -> None:
        validator = WalkForwardValidator.__new__(WalkForwardValidator)
        # required = 10 + 5 * 5 = 35; dataset has 20 rows
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=_dataset(row_count=20),
                time_column="ts",
                train_window=10,
                test_window=5,
                algorithm="arima",
                n_steps=5,
            )

    async def test_rejects_train_window_non_int(self) -> None:
        validator = WalkForwardValidator.__new__(WalkForwardValidator)
        with self.assertRaises(TypeError):
            await validator.process(
                dataset=_dataset(),
                time_column="ts",
                train_window="ten",  # type: ignore[arg-type]
                test_window=5,
                algorithm="arima",
                n_steps=5,
            )
