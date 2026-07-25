"""Mirrored tests for the additive cost-accounting dimension (PIR-512).

Covers :class:`RunBudget.check_cost` and the :class:`RunBudgetMeter` spend
accrual / spend-cap paths (under-cap and over-cap), plus the non-raising
``would_exceed_cost`` downshift predicate — the F22-S6 extension that leaves the
existing iteration/token/deadline behaviour untouched.
"""

from __future__ import annotations

import pytest

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.budget_limit import BudgetLimit
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter


class TestRunBudgetCost:
    def test_none_cost_is_unbounded(self) -> None:
        RunBudget().check_cost(10_000.0)  # no raise

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_cost"):
            RunBudget(max_cost=-1.0)

    def test_bool_cost_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_cost"):
            RunBudget(max_cost=True)  # type: ignore[arg-type]

    def test_cost_breach_raises_typed(self) -> None:
        budget = RunBudget(max_cost=1.0)
        budget.check_cost(1.0)  # at the cap is fine
        with pytest.raises(BudgetBreachError) as excinfo:
            budget.check_cost(1.5)
        assert excinfo.value.limit is BudgetLimit.COST
        assert excinfo.value.spent == 1.5
        assert excinfo.value.allowed == 1.0


class TestMeterCostAccrual:
    def test_under_cap_accrues_without_breach(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=1.0))
        meter.spend_cost(0.4)
        meter.spend_cost(0.5)
        assert meter.cost == pytest.approx(0.9)
        assert meter.remaining_cost == pytest.approx(0.1)
        assert meter.token.cancelled is False

    def test_over_cap_breaches_and_cancels(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=1.0))
        meter.spend_cost(1.0)  # exactly at cap: ok
        with pytest.raises(BudgetBreachError) as excinfo:
            meter.spend_cost(0.01)
        assert excinfo.value.limit is BudgetLimit.COST
        assert meter.token.cancelled is True

    def test_would_exceed_predicate_is_non_raising(self) -> None:
        meter = RunBudgetMeter(RunBudget(max_cost=1.0))
        meter.spend_cost(0.6)
        assert meter.would_exceed_cost(0.5) is True  # 0.6 + 0.5 > 1.0
        assert meter.would_exceed_cost(0.3) is False
        assert meter.cost == pytest.approx(0.6)  # predicate did not accrue

    def test_uncapped_meter_never_exceeds(self) -> None:
        meter = RunBudgetMeter(RunBudget())
        assert meter.would_exceed_cost(10_000.0) is False
        assert meter.remaining_cost is None
