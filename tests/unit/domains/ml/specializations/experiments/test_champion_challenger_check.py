"""Unit tests for :class:`ChampionChallengerCheck`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.champion_challenger_check import (
    ChampionChallengerCheck,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_champion(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ChampionChallengerCheck(
                    champion="bad",  # type: ignore[arg-type]
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="accuracy",
                    _config=KnotConfig(id="ccc"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            ChampionChallengerCheck(
                champion=_KnotStub(_config=KnotConfig(id="ch")),
                challenger=_KnotStub(_config=KnotConfig(id="c")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                primary_metric="accuracy",
                _config=KnotConfig(id="ccc"),
            )
        self.assertIsNotNone(t._store.get("ccc"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ChampionChallengerCheck:
        with Tapestry():
            return ChampionChallengerCheck(
                champion=_KnotStub(_config=KnotConfig(id="ch")),
                challenger=_KnotStub(_config=KnotConfig(id="c")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                primary_metric="accuracy",
                _config=KnotConfig(id="ccc"),
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                champion=object(),  # type: ignore[arg-type]
                challenger=object(),  # type: ignore[arg-type]
                split=object(),  # type: ignore[arg-type]
                primary_metric="",
            )
