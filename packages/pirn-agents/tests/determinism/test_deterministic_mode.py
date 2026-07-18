"""Mirrored tests for seed + frozen-clock deterministic mode (F29-S2)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_agents.determinism.determinism_context import DeterminismContext
from pirn_agents.determinism.deterministic_rng import DeterministicRng
from pirn_agents.determinism.frozen_clock import FrozenClock
from pirn_agents.determinism.system_clock import SystemClock


class FrozenClockTests(unittest.TestCase):
    def test_now_is_fixed_until_advanced(self) -> None:
        clock = FrozenClock(epoch=datetime(2026, 1, 1, tzinfo=UTC))
        first = clock.now()
        assert clock.now() == first
        clock.advance(60)
        assert (clock.now() - first).total_seconds() == 60
        assert clock.monotonic() == 60.0

    def test_naive_epoch_is_treated_as_utc(self) -> None:
        clock = FrozenClock(epoch=datetime(2026, 1, 1))
        assert clock.now().tzinfo is UTC

    def test_advance_rejects_negative(self) -> None:
        with self.assertRaises(ValueError):
            FrozenClock().advance(-1)

    def test_rejects_non_datetime_epoch(self) -> None:
        with self.assertRaises(TypeError):
            FrozenClock(epoch="2026")  # type: ignore[arg-type]


class SystemClockTests(unittest.TestCase):
    def test_now_is_timezone_aware(self) -> None:
        assert SystemClock().now().tzinfo is not None

    def test_monotonic_non_decreasing(self) -> None:
        clock = SystemClock()
        assert clock.monotonic() <= clock.monotonic()


class DeterministicRngTests(unittest.TestCase):
    def test_same_seed_same_stream(self) -> None:
        a = [DeterministicRng(seed=7).random() for _ in range(5)]
        b = [DeterministicRng(seed=7).random() for _ in range(5)]
        assert a == b

    def test_different_seed_diverges(self) -> None:
        assert DeterministicRng(seed=1).random() != DeterministicRng(seed=2).random()

    def test_fork_is_reproducible_and_independent(self) -> None:
        parent = DeterministicRng(seed=99)
        assert parent.fork("a").seed == DeterministicRng(seed=99).fork("a").seed
        assert parent.fork("a").seed != parent.fork("b").seed

    def test_choice_from_empty_raises(self) -> None:
        with self.assertRaises(IndexError):
            DeterministicRng(seed=1).choice([])

    def test_rejects_non_int_seed(self) -> None:
        with self.assertRaises(TypeError):
            DeterministicRng(seed=True)  # type: ignore[arg-type]


class DeterminismContextTests(unittest.TestCase):
    def test_deterministic_is_frozen_and_reproducible(self) -> None:
        ctx = DeterminismContext.deterministic(seed=5)
        assert ctx.is_deterministic
        assert isinstance(ctx.clock, FrozenClock)
        assert ctx.to_payload() == {"seed": 5, "deterministic": True}

    def test_two_deterministic_contexts_produce_identical_output(self) -> None:
        def render(ctx: DeterminismContext) -> list[object]:
            return [ctx.clock.now().isoformat(), ctx.rng.random(), ctx.rng_for("sub").random()]

        assert render(DeterminismContext.deterministic(seed=3)) == render(
            DeterminismContext.deterministic(seed=3)
        )

    def test_live_uses_system_clock(self) -> None:
        ctx = DeterminismContext.live(seed=1)
        assert not ctx.is_deterministic
        assert isinstance(ctx.clock, SystemClock)

    def test_rejects_bad_clock(self) -> None:
        with self.assertRaises(TypeError):
            DeterminismContext(
                clock=object(),  # type: ignore[arg-type]
                rng=DeterministicRng(seed=1),
                deterministic=True,
            )


if __name__ == "__main__":
    unittest.main()
