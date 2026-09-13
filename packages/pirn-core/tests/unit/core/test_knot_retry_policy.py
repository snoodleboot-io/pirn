"""Unit tests for ``KnotRetryPolicy`` (ADR agents-speaks-core, WS0)."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.managers.exception_record import ExceptionRecord


def _record(exc_type: str = "RuntimeError", message: str = "boom") -> ExceptionRecord:
    return ExceptionRecord.for_knot("k", type(exc_type, (Exception,), {})(message))


class TestKnotRetryPolicyConstruction(unittest.TestCase):
    def test_defaults_mean_a_single_attempt(self) -> None:
        policy = KnotRetryPolicy()
        self.assertEqual(policy.max_attempts, 1)
        self.assertTrue(policy.jitter)
        self.assertIsNone(policy.is_retryable)
        self.assertIsNone(policy.retry_after)

    def test_is_frozen(self) -> None:
        policy = KnotRetryPolicy()
        with self.assertRaises(ValidationError):
            policy.max_attempts = 3  # type: ignore[misc]

    def test_rejects_zero_attempts(self) -> None:
        with self.assertRaises(ValidationError):
            KnotRetryPolicy(max_attempts=0)

    def test_rejects_bool_attempts(self) -> None:
        with self.assertRaises(ValidationError):
            KnotRetryPolicy(max_attempts=True)  # type: ignore[arg-type]

    def test_rejects_negative_delays(self) -> None:
        with self.assertRaises(ValidationError):
            KnotRetryPolicy(base_delay=-0.1)
        with self.assertRaises(ValidationError):
            KnotRetryPolicy(max_delay=-0.1)
        with self.assertRaises(ValidationError):
            KnotRetryPolicy(max_retry_after=-0.1)

    def test_rejects_shrinking_multiplier(self) -> None:
        with self.assertRaises(ValidationError):
            KnotRetryPolicy(multiplier=0.5)

    def test_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            KnotRetryPolicy(max_retries=2)  # type: ignore[call-arg]

    def test_callables_are_excluded_from_the_dump(self) -> None:
        policy = KnotRetryPolicy(is_retryable=lambda r: True, retry_after=lambda r: 1.0)
        dumped = policy.model_dump()
        self.assertNotIn("is_retryable", dumped)
        self.assertNotIn("retry_after", dumped)
        self.assertIn("max_attempts", dumped)

    def test_repr_names_the_scalar_fields_only(self) -> None:
        policy = KnotRetryPolicy(max_attempts=3, is_retryable=lambda r: True)
        text = repr(policy)
        self.assertIn("max_attempts=3", text)
        self.assertNotIn("lambda", text)


class TestBackoffDelay(unittest.TestCase):
    def test_grows_exponentially_without_jitter(self) -> None:
        policy = KnotRetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=10.0, jitter=False)
        self.assertEqual([policy.backoff_delay(i) for i in range(4)], [0.1, 0.2, 0.4, 0.8])

    def test_is_capped_at_max_delay(self) -> None:
        policy = KnotRetryPolicy(base_delay=1.0, multiplier=10.0, max_delay=5.0, jitter=False)
        self.assertEqual(policy.backoff_delay(3), 5.0)

    def test_full_jitter_scales_by_the_draw(self) -> None:
        policy = KnotRetryPolicy(base_delay=1.0, multiplier=2.0, max_delay=10.0, jitter=True)
        self.assertEqual(policy.backoff_delay(1, rng=lambda: 0.25), 0.5)
        self.assertEqual(policy.backoff_delay(1, rng=lambda: 0.0), 0.0)

    def test_jitter_draw_is_in_range_by_default(self) -> None:
        policy = KnotRetryPolicy(base_delay=1.0, max_delay=1.0, jitter=True)
        for _ in range(50):
            self.assertLessEqual(0.0, policy.backoff_delay(0))
            self.assertLess(policy.backoff_delay(0), 1.0)


class TestShouldRetry(unittest.TestCase):
    def test_retries_every_err_by_default_while_budget_remains(self) -> None:
        policy = KnotRetryPolicy(max_attempts=3)
        self.assertTrue(policy.should_retry(1, _record()))
        self.assertTrue(policy.should_retry(2, _record()))

    def test_stops_once_attempts_are_spent(self) -> None:
        policy = KnotRetryPolicy(max_attempts=3)
        self.assertFalse(policy.should_retry(3, _record()))
        self.assertFalse(policy.should_retry(4, _record()))

    def test_single_attempt_policy_never_retries(self) -> None:
        self.assertFalse(KnotRetryPolicy().should_retry(1, _record()))

    def test_predicate_decides_on_the_record(self) -> None:
        policy = KnotRetryPolicy(
            max_attempts=5, is_retryable=lambda r: r.exc_type == "RateLimitError"
        )
        self.assertTrue(policy.should_retry(1, _record("RateLimitError")))
        self.assertFalse(policy.should_retry(1, _record("ValueError")))

    def test_predicate_is_not_consulted_once_spent(self) -> None:
        calls: list[ExceptionRecord] = []
        policy = KnotRetryPolicy(max_attempts=1, is_retryable=lambda r: calls.append(r) or True)
        self.assertFalse(policy.should_retry(1, _record()))
        self.assertEqual(calls, [])


class TestDelayBeforeRetry(unittest.TestCase):
    def test_uses_backoff_without_a_hint(self) -> None:
        policy = KnotRetryPolicy(base_delay=0.3, jitter=False)
        self.assertEqual(policy.delay_before_retry(0, _record()), 0.3)

    def test_a_hint_wins_over_backoff(self) -> None:
        policy = KnotRetryPolicy(base_delay=0.3, jitter=False, retry_after=lambda r: 7.0)
        self.assertEqual(policy.delay_before_retry(0, _record()), 7.0)

    def test_a_hint_is_capped(self) -> None:
        policy = KnotRetryPolicy(max_retry_after=2.0, retry_after=lambda r: 600.0)
        self.assertEqual(policy.delay_before_retry(0, _record()), 2.0)

    def test_a_missing_hint_falls_back_to_backoff(self) -> None:
        policy = KnotRetryPolicy(base_delay=0.3, jitter=False, retry_after=lambda r: None)
        self.assertEqual(policy.delay_before_retry(0, _record()), 0.3)
