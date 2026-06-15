"""Unit tests for :class:`Plan`."""

from __future__ import annotations

import unittest

from pirn_agents.types.plan import Plan


class TestRoundtrip(unittest.TestCase):
    def test_default_rationale_is_empty(self) -> None:
        plan = Plan(steps=("step a", "step b"))
        assert plan.steps == ("step a", "step b")
        assert plan.rationale == ""

    def test_construct_with_rationale(self) -> None:
        plan = Plan(steps=("a",), rationale="because")
        assert plan.rationale == "because"

    def test_audit_dict_round_trip(self) -> None:
        plan = Plan(steps=("a", "b"), rationale="why")
        d = plan._pirn_audit_dict()
        assert d == {"steps": ["a", "b"], "rationale": "why"}
