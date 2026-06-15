"""Unit tests for :class:`BaselineEstablisher`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.baseline_establisher import (
    BaselineEstablisher,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_split(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                BaselineEstablisher(
                    split="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="be"),
                )

    def test_valid_construction_defaults(self) -> None:
        with Tapestry() as t:
            BaselineEstablisher(
                split=_KnotStub(_config=KnotConfig(id="s")),
                _config=KnotConfig(id="be"),
            )
        self.assertIsNotNone(t._store.get("be"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BaselineEstablisher:
        with Tapestry():
            return BaselineEstablisher(
                split=_KnotStub(_config=KnotConfig(id="s")),
                _config=KnotConfig(id="be"),
            )

    async def test_rejects_empty_algorithm(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="",
                metrics=("accuracy",),
            )

    async def test_rejects_empty_metrics(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                split=object(),  # type: ignore[arg-type]
                algorithm="linear",
                metrics=[],
            )
