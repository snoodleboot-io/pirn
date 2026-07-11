"""Unit tests for :class:`pirn_agents.llm.rate_limit_error.RateLimitError`."""

from __future__ import annotations

import unittest

from pirn_agents.llm.rate_limit_error import RateLimitError


class TestRateLimitError(unittest.TestCase):
    def test_defaults(self) -> None:
        error = RateLimitError("rate limited")
        assert error.retry_after is None
        assert error.status_code == 429

    def test_carries_retry_after(self) -> None:
        error = RateLimitError("rate limited", retry_after=2.5)
        assert error.retry_after == 2.5

    def test_message_preserved(self) -> None:
        assert str(RateLimitError("too many")) == "too many"


if __name__ == "__main__":
    unittest.main()
