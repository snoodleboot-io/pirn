"""Unit tests for :class:`TokenCounter` — estimation and cache behaviour."""

from __future__ import annotations

import unittest

from pirn_agents.context.heuristic_token_estimator import HeuristicTokenEstimator
from pirn_agents.context.token_counter import TokenCounter
from pirn_agents.types.agent_message import AgentMessage
from tests.context._stubs import StubWordTokenEstimator


class TestCount(unittest.TestCase):
    def test_uses_injected_provider_strategy(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator())
        assert counter.count("one two three") == 3

    def test_heuristic_provider_strategy(self) -> None:
        counter = TokenCounter(estimator=HeuristicTokenEstimator(chars_per_token=2.0))
        assert counter.count("abcd") == 2

    def test_estimator_property(self) -> None:
        est = StubWordTokenEstimator(name="p")
        counter = TokenCounter(estimator=est)
        assert counter.estimator is est


class TestCacheBehaviour(unittest.TestCase):
    def test_repeated_text_hits_cache_and_skips_estimator(self) -> None:
        est = StubWordTokenEstimator()
        counter = TokenCounter(estimator=est)
        counter.count("a b c")
        counter.count("a b c")
        counter.count("a b c")
        # The estimator was only consulted on the first (cold) call.
        assert est.estimate_calls == ["a b c"]
        assert counter.cache_info() == {"hits": 2, "misses": 1, "size": 1}

    def test_distinct_text_misses(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator())
        counter.count("a")
        counter.count("b")
        info = counter.cache_info()
        assert info["misses"] == 2
        assert info["hits"] == 0
        assert info["size"] == 2

    def test_clear_cache_resets_stats(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator())
        counter.count("a")
        counter.count("a")
        counter.clear_cache()
        assert counter.cache_info() == {"hits": 0, "misses": 0, "size": 0}
        # After clearing, the same text is a cold miss again.
        counter.count("a")
        assert counter.cache_info()["misses"] == 1


class TestCountMessages(unittest.TestCase):
    def test_adds_per_message_overhead(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=2)
        message = AgentMessage(role="user", content="one two")
        # 2 content tokens + 2 overhead.
        assert counter.count_message(message) == 4

    def test_count_messages_sums(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=1)
        messages = (
            AgentMessage(role="user", content="one two"),
            AgentMessage(role="assistant", content="three"),
        )
        # (2 + 1) + (1 + 1) == 5.
        assert counter.count_messages(messages) == 5

    def test_count_messages_empty(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator())
        assert counter.count_messages(()) == 0


class TestValidation(unittest.TestCase):
    def test_rejects_non_estimator(self) -> None:
        with self.assertRaisesRegex(TypeError, "estimator"):
            TokenCounter(estimator=object())  # type: ignore[arg-type]

    def test_rejects_negative_overhead(self) -> None:
        with self.assertRaisesRegex(ValueError, "per_message_overhead"):
            TokenCounter(estimator=StubWordTokenEstimator(), per_message_overhead=-1)

    def test_rejects_non_str_text(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator())
        with self.assertRaisesRegex(TypeError, "text"):
            counter.count(5)  # type: ignore[arg-type]

    def test_rejects_non_message(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator())
        with self.assertRaisesRegex(TypeError, "message"):
            counter.count_message("nope")  # type: ignore[arg-type]

    def test_rejects_non_sequence_messages(self) -> None:
        counter = TokenCounter(estimator=StubWordTokenEstimator())
        with self.assertRaisesRegex(TypeError, "messages"):
            counter.count_messages(42)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
