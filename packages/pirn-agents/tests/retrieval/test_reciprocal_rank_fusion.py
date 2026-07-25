"""Tests for :func:`reciprocal_rank_fusion`."""

from __future__ import annotations

import unittest

from pirn_agents.retrieval.reciprocal_rank_fusion import reciprocal_rank_fusion


class TestReciprocalRankFusion(unittest.TestCase):
    def test_rejects_non_positive_k(self) -> None:
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([["a"]], k=0)

    def test_empty_input_returns_empty(self) -> None:
        assert reciprocal_rank_fusion([]) == []

    def test_item_in_both_rankings_beats_single_list_item(self) -> None:
        dense = ["a", "b", "c"]
        lexical = ["b", "d", "e"]
        fused = dict(reciprocal_rank_fusion([dense, lexical]))
        # b appears in both lists, so it must outrank a (only in one)
        assert fused["b"] > fused["a"]

    def test_order_is_descending_by_fused_score(self) -> None:
        fused = reciprocal_rank_fusion([["a", "b"], ["b", "a"]])
        scores = [score for _, score in fused]
        assert scores == sorted(scores, reverse=True)

    def test_ties_break_by_first_appearance(self) -> None:
        # x and y each appear once at rank 0 of a distinct list -> equal scores;
        # x appears first overall so it comes first.
        fused = reciprocal_rank_fusion([["x"], ["y"]])
        assert [identifier for identifier, _ in fused] == ["x", "y"]

    def test_larger_k_flattens_contribution(self) -> None:
        small = dict(reciprocal_rank_fusion([["a", "b"]], k=1))
        large = dict(reciprocal_rank_fusion([["a", "b"]], k=1000))
        # top-rank advantage over rank-2 shrinks as k grows
        assert (small["a"] - small["b"]) > (large["a"] - large["b"])


if __name__ == "__main__":
    unittest.main()
