"""Unit tests for the :class:`ConsensusStrategy` interface base."""

from __future__ import annotations

import unittest

from pirn_agents.specializations.multi_agent.consensus_strategy import ConsensusStrategy
from tests.specializations.conftest import StubLLMProvider


class _NamedStrategy(ConsensusStrategy):
    def name(self) -> str:
        return "named"


class TestConsensusStrategyInterface(unittest.TestCase):
    def test_name_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "name"):
            ConsensusStrategy().name()

    def test_build_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "build"):
            _NamedStrategy().build(responses={}, llm=StubLLMProvider(["x"]))

    def test_matches_delegates_to_name(self) -> None:
        strategy = _NamedStrategy()

        assert strategy.matches("named")
        assert not strategy.matches("other")


if __name__ == "__main__":
    unittest.main()
