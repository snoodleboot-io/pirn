"""Tests for MermaidRenderer."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.viz.mermaid_renderer import MermaidRenderer


def _make_tapestry(*knots):
    t = MagicMock()
    t.store.all.return_value = list(knots)
    return t


class _FakeKnot:
    """The three things a renderer asks a knot for: its id, parents and kind."""

    _knot_kind = "knot"

    def __init__(self, knot_id: str, parents=None):
        self.knot_id = knot_id
        self.parents = parents or {}

    @classmethod
    def knot_kind(cls) -> str:
        return cls._knot_kind


class _FakeContainerKnot(_FakeKnot):
    """A knot that declares itself a container, as ``SubTapestry`` does."""

    _knot_kind = "sub_tapestry"


def _make_knot(knot_id: str, parents=None, klass=None):
    return (klass or _FakeKnot)(knot_id, parents)


class TestMermaidRendererSafeNodeId(unittest.TestCase):
    def test_plain_identifier_unchanged(self) -> None:
        self.assertEqual(MermaidRenderer._safe_node_id("my_node"), "my_node")

    def test_special_chars_replaced(self) -> None:
        result = MermaidRenderer._safe_node_id("my-node.id")
        self.assertNotIn("-", result)
        self.assertNotIn(".", result)

    def test_digit_prefix_prefixed(self) -> None:
        result = MermaidRenderer._safe_node_id("1bad")
        self.assertTrue(result.startswith("n_"))

    def test_empty_string_becomes_underscore(self) -> None:
        result = MermaidRenderer._safe_node_id("")
        self.assertEqual(result, "_")

    def test_colon_replaced(self) -> None:
        result = MermaidRenderer._safe_node_id("ns:name")
        self.assertNotIn(":", result)


class TestMermaidRendererNodeLabel(unittest.TestCase):
    def test_label_contains_id_and_class(self) -> None:
        label = MermaidRenderer._node_label("my_knot", "MyKnot")
        self.assertIn("my_knot", label)
        self.assertIn("MyKnot", label)

    def test_embedded_double_quotes_escaped(self) -> None:
        label = MermaidRenderer._node_label('say "hi"', "Klass")
        self.assertNotIn('"hi"', label)


class TestMermaidRendererShortClass(unittest.TestCase):
    def test_last_segment(self) -> None:
        self.assertEqual(MermaidRenderer._short_class("pirn.nodes.MyKnot"), "MyKnot")

    def test_bare_name(self) -> None:
        self.assertEqual(MermaidRenderer._short_class("MyKnot"), "MyKnot")


class TestMermaidForTapestry(unittest.TestCase):
    def test_empty_tapestry(self) -> None:
        tapestry = _make_tapestry()
        result = MermaidRenderer.for_tapestry(tapestry)
        self.assertIn("graph TD", result)

    def test_single_node(self) -> None:
        k = _make_knot("source1")
        tapestry = _make_tapestry(k)
        result = MermaidRenderer.for_tapestry(tapestry)
        self.assertIn("graph TD", result)
        self.assertIn("source1", result)

    def test_edge_rendered(self) -> None:
        k1 = _make_knot("src")
        k2 = _make_knot("transform", parents={"data": k1})
        tapestry = _make_tapestry(k1, k2)
        result = MermaidRenderer.for_tapestry(tapestry)
        self.assertIn("-->", result)

    def test_wrapper_function(self) -> None:
        tapestry = _make_tapestry()
        result = MermaidRenderer.for_tapestry(tapestry)
        self.assertIn("graph TD", result)


class TestMermaidContainerShape(unittest.TestCase):
    def test_a_container_kind_gets_the_subroutine_shape(self) -> None:
        tapestry = _make_tapestry(_make_knot("inner", klass=_FakeContainerKnot))
        result = MermaidRenderer.for_tapestry(tapestry)
        self.assertIn("inner[[", result)

    def test_a_leaf_kind_gets_the_plain_shape(self) -> None:
        tapestry = _make_tapestry(_make_knot("leaf"))
        result = MermaidRenderer.for_tapestry(tapestry)
        self.assertNotIn("leaf[[", result)
        self.assertIn('leaf["', result)
