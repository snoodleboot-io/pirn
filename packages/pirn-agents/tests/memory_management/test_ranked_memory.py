"""Unit tests for :class:`RankedMemory`."""

from __future__ import annotations

import unittest

from pirn_agents.memory_management.ranked_memory import RankedMemory
from tests.memory_management.conftest import make_record


class TestRankedMemory(unittest.TestCase):
    def test_audit_dict_exposes_components(self) -> None:
        ranked = RankedMemory(
            record=make_record(id="r1"),
            score=1.5,
            relevance=0.5,
            recency=0.6,
            importance=0.4,
        )
        audit = ranked._pirn_audit_dict()
        assert audit["record"] == "r1"
        assert audit["score"] == 1.5
        assert audit["relevance"] == 0.5
