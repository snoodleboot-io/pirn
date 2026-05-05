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
    def test_rejects_k_less_than_2(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                GroupKFoldCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="rf",
                    metrics=["accuracy"],
                    group_column="patient_id",
                    k=1,
                    _config=KnotConfig(id="gkf"),
                )

    def test_rejects_empty_group_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                GroupKFoldCrossValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    algorithm="rf",
                    metrics=["accuracy"],
                    group_column="",
                    _config=KnotConfig(id="gkf"),
                )

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
