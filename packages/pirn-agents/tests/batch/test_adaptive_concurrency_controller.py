"""Mirrored tests for the F28-S2 AIMD concurrency controller."""

from __future__ import annotations

import pytest

from pirn_agents.batch.adaptive_concurrency_controller import AdaptiveConcurrencyController


class TestAimdBehaviour:
    def test_starts_at_max_by_default(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8)
        assert controller.limit() == 8

    def test_throttle_halves_limit(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8, decrease_factor=0.5)
        controller.on_throttle()
        assert controller.limit() == 4
        controller.on_throttle()
        assert controller.limit() == 2

    def test_success_additively_increases(self) -> None:
        controller = AdaptiveConcurrencyController(
            min_limit=1, max_limit=8, initial=2, increase=1.0
        )
        controller.on_success()
        assert controller.limit() == 3

    def test_never_drops_below_min(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=2, max_limit=8, decrease_factor=0.1)
        for _ in range(10):
            controller.on_throttle()
        assert controller.limit() == 2

    def test_never_climbs_above_max(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=4, initial=4)
        for _ in range(10):
            controller.on_success()
        assert controller.limit() == 4

    def test_converges_back_up_after_throttle(self) -> None:
        controller = AdaptiveConcurrencyController(min_limit=1, max_limit=8, initial=8)
        controller.on_throttle()  # 8 -> 4
        assert controller.limit() == 4
        controller.on_success()  # 4 -> 5
        controller.on_success()  # 5 -> 6
        assert controller.limit() == 6


class TestValidation:
    def test_rejects_min_below_one(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=0, max_limit=4)

    def test_rejects_max_below_min(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=4, max_limit=2)

    def test_rejects_decrease_factor_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=1, max_limit=4, decrease_factor=1.5)

    def test_rejects_non_positive_increase(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=1, max_limit=4, increase=0)

    def test_rejects_initial_out_of_bounds(self) -> None:
        with pytest.raises(ValueError):
            AdaptiveConcurrencyController(min_limit=1, max_limit=4, initial=9)
