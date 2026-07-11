"""Tests for the pure-Python :class:`Bm25Index`."""

from __future__ import annotations

import unittest

from pirn_agents.retrieval.bm25_index import Bm25Index


class TestBm25Index(unittest.TestCase):
    def _corpus(self) -> Bm25Index:
        index = Bm25Index()
        index.add("d1", "the quick brown fox jumps")
        index.add("d2", "a lazy brown dog sleeps")
        index.add("d3", "quantum entanglement in physics")
        return index

    def test_rejects_bad_parameters(self) -> None:
        with self.assertRaises(ValueError):
            Bm25Index(k1=-1.0)
        with self.assertRaises(ValueError):
            Bm25Index(b=1.5)

    def test_empty_index_returns_empty(self) -> None:
        assert Bm25Index().search("anything") == []

    def test_ranks_keyword_document_first(self) -> None:
        index = self._corpus()
        results = index.search("quantum physics")
        assert results
        assert results[0][0] == "d3"

    def test_shared_term_ranks_both_but_orders_by_relevance(self) -> None:
        index = self._corpus()
        results = dict(index.search("brown fox"))
        # both d1 and d2 contain "brown"; only d1 contains "fox"
        assert "d1" in results and "d2" in results
        assert results["d1"] > results["d2"]

    def test_non_matching_query_scores_nothing(self) -> None:
        index = self._corpus()
        assert index.search("unrelated vocabulary") == []

    def test_top_k_limits_results(self) -> None:
        index = self._corpus()
        assert len(index.search("brown", top_k=1)) == 1

    def test_rejects_non_positive_top_k(self) -> None:
        with self.assertRaises(ValueError):
            self._corpus().search("brown", top_k=0)

    def test_readding_replaces_document(self) -> None:
        index = Bm25Index()
        index.add("d1", "brown fox")
        index.add("d1", "grey wolf")
        assert index.search("fox") == []
        assert index.search("wolf")[0][0] == "d1"


if __name__ == "__main__":
    unittest.main()
