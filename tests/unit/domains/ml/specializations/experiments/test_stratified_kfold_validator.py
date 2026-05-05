"""Unit tests for :class:`StratifiedKFoldValidator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.stratified_kfold_validator import (
    StratifiedKFoldValidator,
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
                StratifiedKFoldValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    stratify_column="label",
                    algorithm="rf",
                    metrics=["accuracy"],
                    k=1,
                    _config=KnotConfig(id="skf"),
                )

    def test_rejects_empty_stratify_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                StratifiedKFoldValidator(
                    dataset=_KnotStub(_config=KnotConfig(id="d")),
                    stratify_column="",
                    algorithm="rf",
                    metrics=["accuracy"],
                    _config=KnotConfig(id="skf"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            StratifiedKFoldValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                stratify_column="label",
                algorithm="rf",
                metrics=["accuracy"],
                k=5,
                _config=KnotConfig(id="skf"),
            )
        self.assertIsNotNone(t._store.get("skf"))
