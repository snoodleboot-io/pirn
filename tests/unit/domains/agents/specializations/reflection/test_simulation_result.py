"""Unit tests for :class:`SimulationResult`."""

from __future__ import annotations

import unittest

from pirn.domains.agents.specializations.reflection.simulation_result import (
    SimulationResult,
)


class TestSimulationResult(unittest.TestCase):
    def test_construction_and_attributes(self) -> None:
        sr = SimulationResult(
            best_case="all goes well",
            neutral_case="moderate outcome",
            worst_case="catastrophic failure",
        )
        assert sr.best_case == "all goes well"
        assert sr.neutral_case == "moderate outcome"
        assert sr.worst_case == "catastrophic failure"

    def test_is_frozen(self) -> None:
        sr = SimulationResult(
            best_case="good",
            neutral_case="ok",
            worst_case="bad",
        )
        with self.assertRaises((AttributeError, TypeError)):
            sr.best_case = "modified"  # type: ignore[misc]

    def test_pirn_audit_dict(self) -> None:
        sr = SimulationResult(
            best_case="good",
            neutral_case="neutral",
            worst_case="bad",
        )
        d = sr._pirn_audit_dict()
        assert d["best_case"] == "good"
        assert d["neutral_case"] == "neutral"
        assert d["worst_case"] == "bad"

    def test_equality(self) -> None:
        a = SimulationResult(best_case="g", neutral_case="n", worst_case="b")
        b = SimulationResult(best_case="g", neutral_case="n", worst_case="b")
        assert a == b
