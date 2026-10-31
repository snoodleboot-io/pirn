"""Unit tests for :class:`Plan` (``Payload[PlanFrame, tuple[str, ...]]``, PIR-874)."""

from __future__ import annotations

import unittest

from pirn.core.payload import Payload

from pirn_agents.planning.plan import Plan
from pirn_agents.planning.plan_frame import PlanFrame


class TestPlan(unittest.TestCase):
    def test_is_payload_with_frame(self) -> None:
        plan = Plan(steps=("a", "b"), rationale="why")
        assert isinstance(plan, Payload)
        assert isinstance(plan.metadata, PlanFrame)

    def test_default_rationale_is_empty(self) -> None:
        plan = Plan(steps=["step a", "step b"])
        assert plan.data == ("step a", "step b")
        assert plan.metadata.rationale == ""

    def test_construct_with_rationale(self) -> None:
        assert Plan(steps=("a",), rationale="because").metadata.rationale == "because"

    def test_audit_dict_has_both_halves(self) -> None:
        d = Plan(steps=("a", "b"), rationale="why")._pirn_audit_dict()
        assert d == {"rationale": "why", "steps": ["a", "b"]}

    def test_equal_plans_compare_equal(self) -> None:
        assert Plan(steps=("a",), rationale="r") == Plan(steps=("a",), rationale="r")

    def test_different_plans_compare_unequal(self) -> None:
        assert Plan(steps=("a",), rationale="r") != Plan(steps=("b",), rationale="r")
        assert Plan(steps=("a",), rationale="r") != Plan(steps=("a",), rationale="s")
