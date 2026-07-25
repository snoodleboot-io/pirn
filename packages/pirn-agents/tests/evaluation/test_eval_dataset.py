"""Tests for :class:`EvalItem` / :class:`EvalDataset` schema and JSON round-trip."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.eval_dataset import EvalDataset
from pirn_agents.evaluation.eval_item import EvalItem


class EvalItemTests(unittest.TestCase):
    def test_stores_fields_with_defaults(self) -> None:
        item = EvalItem(item_id="a", input={"q": "x"})
        assert item.item_id == "a"
        assert item.input == {"q": "x"}
        assert item.expected == {}
        assert item.metadata == {}

    def test_non_str_id_raises(self) -> None:
        with self.assertRaises(TypeError):
            EvalItem(item_id=1, input={})  # type: ignore[arg-type]

    def test_non_mapping_input_raises(self) -> None:
        with self.assertRaises(TypeError):
            EvalItem(item_id="a", input=[1])  # type: ignore[arg-type]


class EvalDatasetTests(unittest.TestCase):
    def test_normalizes_items_to_tuple(self) -> None:
        ds = EvalDataset(items=[EvalItem(item_id="a", input={})])
        assert isinstance(ds.items, tuple)
        assert len(ds) == 1

    def test_duplicate_item_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            EvalDataset(items=[EvalItem(item_id="a", input={}), EvalItem(item_id="a", input={})])

    def test_non_item_element_raises(self) -> None:
        with self.assertRaises(TypeError):
            EvalDataset(items=["nope"])  # type: ignore[list-item]

    def test_json_roundtrip(self) -> None:
        ds = EvalDataset(
            items=[
                EvalItem(
                    item_id="a",
                    input={"q": "capital of france"},
                    expected={"answer": "Paris"},
                    metadata={"difficulty": "easy"},
                ),
                EvalItem(item_id="b", input={"q": "2+2"}, expected={"answer": "4"}),
            ]
        )
        restored = EvalDataset.from_json(ds.to_json())
        assert restored == ds


if __name__ == "__main__":
    unittest.main()
