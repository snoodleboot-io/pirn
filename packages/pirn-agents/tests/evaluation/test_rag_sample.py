"""Tests for :class:`RagSample` validation and audit form."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.rag_sample import RagSample


class RagSampleTests(unittest.TestCase):
    def test_stores_fields_and_normalizes_contexts_to_tuple(self) -> None:
        sample = RagSample(query="q", contexts=["a", "b"], answer="ans", ground_truth="gt")
        assert sample.query == "q"
        assert sample.contexts == ("a", "b")
        assert sample.answer == "ans"
        assert sample.ground_truth == "gt"

    def test_defaults(self) -> None:
        sample = RagSample(query="q")
        assert sample.contexts == ()
        assert sample.answer == ""
        assert sample.ground_truth is None

    def test_contexts_as_bare_str_raises(self) -> None:
        with self.assertRaises(TypeError):
            RagSample(query="q", contexts="not-a-list")  # type: ignore[arg-type]

    def test_non_str_context_element_raises(self) -> None:
        with self.assertRaises(TypeError):
            RagSample(query="q", contexts=["ok", 5])  # type: ignore[list-item]

    def test_non_str_query_raises(self) -> None:
        with self.assertRaises(TypeError):
            RagSample(query=1)  # type: ignore[arg-type]

    def test_non_str_ground_truth_raises(self) -> None:
        with self.assertRaises(TypeError):
            RagSample(query="q", ground_truth=5)  # type: ignore[arg-type]

    def test_audit_dict_is_primitive(self) -> None:
        sample = RagSample(query="q", contexts=["a"], answer="x", ground_truth="g")
        assert sample._pirn_audit_dict() == {
            "query": "q",
            "contexts": ["a"],
            "answer": "x",
            "ground_truth": "g",
        }


if __name__ == "__main__":
    unittest.main()
