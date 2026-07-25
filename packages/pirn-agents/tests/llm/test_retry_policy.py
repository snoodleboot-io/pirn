"""Unit tests for :class:`pirn_agents.llm.retry_policy.RetryPolicy`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.retry_policy import RetryPolicy


class TestRetryPolicy(unittest.TestCase):
    def test_defaults(self) -> None:
        policy = RetryPolicy()
        assert policy.max_retries == 2
        assert policy.jitter is True

    def test_backoff_grows_exponentially_without_jitter(self) -> None:
        policy = RetryPolicy(base_delay=0.1, multiplier=2.0, max_delay=10.0, jitter=False)
        assert policy.backoff_delay(0) == 0.1
        assert policy.backoff_delay(1) == 0.2
        assert policy.backoff_delay(2) == 0.4

    def test_backoff_is_capped(self) -> None:
        policy = RetryPolicy(base_delay=1.0, multiplier=10.0, max_delay=5.0, jitter=False)
        assert policy.backoff_delay(3) == 5.0

    def test_full_jitter_scales_capped_delay(self) -> None:
        policy = RetryPolicy(base_delay=1.0, multiplier=1.0, max_delay=2.0, jitter=True)
        # rng=1.0 -> full capped delay; rng=0.0 -> zero.
        assert policy.backoff_delay(0, rng=lambda: 1.0) == 1.0
        assert policy.backoff_delay(0, rng=lambda: 0.0) == 0.0
        assert policy.backoff_delay(0, rng=lambda: 0.5) == 0.5

    def test_audit_dict_is_secret_free_and_stable(self) -> None:
        policy = RetryPolicy(max_retries=3)
        audit = policy._pirn_audit_dict()
        assert audit["max_retries"] == 3
        assert set(audit) == {"max_retries", "base_delay", "max_delay", "multiplier", "jitter"}


if __name__ == "__main__":
    unittest.main()
