"""Unit tests for :class:`GroupKFoldCrossValidator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.group_kfold_cross_validator import (
    GroupKFoldCrossValidator,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            GroupKFoldCrossValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=5,
                _config=KnotConfig(id="gkf"),
            )
        self.assertIsNotNone(t._store.get("gkf"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GroupKFoldCrossValidator:
        with Tapestry():
            return GroupKFoldCrossValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=5,
                _config=KnotConfig(id="gkf"),
            )

    async def test_rejects_k_less_than_2(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                dataset=object(),  # type: ignore[arg-type]
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=1,
            )

    async def test_rejects_empty_group_column(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                dataset=object(),  # type: ignore[arg-type]
                algorithm="rf",
                metrics=["accuracy"],
                group_column="",
                k=5,
            )
