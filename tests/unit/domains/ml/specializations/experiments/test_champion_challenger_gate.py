"""Unit tests for :class:`ChampionChallengerGate`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.champion_challenger_gate import (
    ChampionChallengerGate,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_champion(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ChampionChallengerGate(
                    champion="bad",  # type: ignore[arg-type]
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="accuracy",
                    _config=KnotConfig(id="ccg"),
                )

    def test_rejects_empty_primary_metric(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ChampionChallengerGate(
                    champion=_KnotStub(_config=KnotConfig(id="ch")),
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="",
                    _config=KnotConfig(id="ccg"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            ChampionChallengerGate(
                champion=_KnotStub(_config=KnotConfig(id="ch")),
                challenger=_KnotStub(_config=KnotConfig(id="c")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                primary_metric="accuracy",
                _config=KnotConfig(id="ccg"),
            )
        self.assertIsNotNone(t._store.get("ccg"))
