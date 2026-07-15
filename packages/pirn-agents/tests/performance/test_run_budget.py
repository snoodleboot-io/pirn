"""Unit tests for :class:`RunBudget` validation and per-dimension breach checks."""

from __future__ import annotations

import dataclasses

import pytest

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.budget_limit import BudgetLimit
from pirn_agents.performance.run_budget import RunBudget


class TestValidation:
    def test_all_none_is_unbounded(self) -> None:
        budget = RunBudget()
        # No dimension raises regardless of spend.
        budget.check_iterations(10_000)
        budget.check_tokens(10_000)
        budget.check_deadline(10_000.0)

    @pytest.mark.parametrize("field", ["max_iterations", "max_tokens"])
    def test_negative_int_fields_rejected(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            RunBudget(**{field: -1})

    @pytest.mark.parametrize("field", ["max_iterations", "max_tokens"])
    def test_bool_int_fields_rejected(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            RunBudget(**{field: True})

    def test_negative_deadline_rejected(self) -> None:
        with pytest.raises(ValueError, match="deadline_seconds"):
            RunBudget(deadline_seconds=-0.5)

    def test_frozen(self) -> None:
        budget = RunBudget(max_iterations=3)
        with pytest.raises(dataclasses.FrozenInstanceError):
            budget.max_iterations = 5  # type: ignore[misc]


class TestChecks:
    def test_iteration_breach_raises_typed(self) -> None:
        budget = RunBudget(max_iterations=2)
        budget.check_iterations(2)  # at the cap is fine
        with pytest.raises(BudgetBreachError) as excinfo:
            budget.check_iterations(3)
        assert excinfo.value.limit is BudgetLimit.ITERATIONS
        assert excinfo.value.spent == 3
        assert excinfo.value.allowed == 2

    def test_token_breach_raises_typed(self) -> None:
        budget = RunBudget(max_tokens=100)
        budget.check_tokens(100)
        with pytest.raises(BudgetBreachError) as excinfo:
            budget.check_tokens(101)
        assert excinfo.value.limit is BudgetLimit.TOKENS

    def test_deadline_breach_raises_typed(self) -> None:
        budget = RunBudget(deadline_seconds=1.0)
        budget.check_deadline(1.0)
        with pytest.raises(BudgetBreachError) as excinfo:
            budget.check_deadline(1.5)
        assert excinfo.value.limit is BudgetLimit.DEADLINE

    def test_audit_dict_is_flat_primitives(self) -> None:
        budget = RunBudget(max_iterations=1, max_tokens=2, deadline_seconds=3.0, max_cost=4.0)
        assert budget._pirn_audit_dict() == {
            "max_iterations": 1,
            "max_tokens": 2,
            "deadline_seconds": 3.0,
            "max_cost": 4.0,
        }

    def test_equal_budgets_hash_equal(self) -> None:
        assert RunBudget(max_iterations=5) == RunBudget(max_iterations=5)
