"""Unit tests for the deprecated :class:`ChampionChallengerGate` alias.

``ChampionChallengerGate`` was renamed to ``ChampionChallengerCheck`` (R9).
These tests cover only the alias-specific behaviour — the deprecation
warning and behavioural identity with ``ChampionChallengerCheck``. Full
functional coverage lives in ``test_champion_challenger_check.py``.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.champion_challenger_check import (
    ChampionChallengerCheck,
)
from pirn_ml.specializations.experiments.champion_challenger_gate import (
    ChampionChallengerGate,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestDeprecation(unittest.TestCase):
    def test_construction_emits_deprecation_warning(self) -> None:
        with Tapestry():
            with self.assertWarns(DeprecationWarning):
                ChampionChallengerGate(
                    champion=_KnotStub(_config=KnotConfig(id="ch")),
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="accuracy",
                    _config=KnotConfig(id="ccc"),
                )

    def test_is_a_champion_challenger_check(self) -> None:
        with Tapestry():
            with self.assertWarns(DeprecationWarning):
                gate = ChampionChallengerGate(
                    champion=_KnotStub(_config=KnotConfig(id="ch")),
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="accuracy",
                    _config=KnotConfig(id="ccc"),
                )
        assert isinstance(gate, ChampionChallengerCheck)


class TestIdenticalOutput(unittest.IsolatedAsyncioTestCase):
    async def test_process_output_matches_check(self) -> None:
        with Tapestry():
            with self.assertWarns(DeprecationWarning):
                gate = ChampionChallengerGate(
                    champion=_KnotStub(_config=KnotConfig(id="ch")),
                    challenger=_KnotStub(_config=KnotConfig(id="c")),
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    primary_metric="accuracy",
                    _config=KnotConfig(id="ccc"),
                )
        with Tapestry():
            check = ChampionChallengerCheck(
                champion=_KnotStub(_config=KnotConfig(id="ch")),
                challenger=_KnotStub(_config=KnotConfig(id="c")),
                split=_KnotStub(_config=KnotConfig(id="s")),
                primary_metric="accuracy",
                _config=KnotConfig(id="ccc"),
            )

        gate_error: Exception | None = None
        check_error: Exception | None = None
        try:
            await gate.process(
                champion=object(),  # type: ignore[arg-type]
                challenger=object(),  # type: ignore[arg-type]
                split=object(),  # type: ignore[arg-type]
                primary_metric="",
            )
        except ValueError as exc:
            gate_error = exc
        try:
            await check.process(
                champion=object(),  # type: ignore[arg-type]
                challenger=object(),  # type: ignore[arg-type]
                split=object(),  # type: ignore[arg-type]
                primary_metric="",
            )
        except ValueError as exc:
            check_error = exc

        assert gate_error is not None
        assert check_error is not None
        assert str(gate_error) == str(check_error)
