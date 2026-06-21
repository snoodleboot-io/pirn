"""Tests for TapestryHtmlRenderer."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.viz.html import TapestryHtmlRenderer, html_for_tapestry


def _make_tapestry(*knots):
    t = MagicMock()
    t._store.all.return_value = list(knots)
    t.store = t._store
    return t


def _make_knot(knot_id: str, parents=None):
    k = MagicMock()
    k.knot_id = knot_id
    k.parents = parents or {}
    k.__class__ = type("MockKnot", (), {})
    return k


class TestTapestryHtmlRendererLayerNodes(unittest.TestCase):
    def test_empty_produces_empty_layers(self) -> None:
        layers = TapestryHtmlRenderer._layer_nodes([], [])
        self.assertEqual(layers, [])

    def test_single_node_in_one_layer(self) -> None:
        nodes = [{"id": "a", "outcome": "ok"}]
        layers = TapestryHtmlRenderer._layer_nodes(nodes, [])
        self.assertEqual(len(layers), 1)
        self.assertIn("a", layers[0])

    def test_chain_produces_two_layers(self) -> None:
        nodes = [{"id": "a"}, {"id": "b"}]
        edges = [{"from": "a", "to": "b"}]
        layers = TapestryHtmlRenderer._layer_nodes(nodes, edges)
        self.assertEqual(len(layers), 2)
        self.assertIn("a", layers[0])
        self.assertIn("b", layers[1])


class TestTapestryHtmlRendererAssignCoords(unittest.TestCase):
    def test_single_node_gets_coords(self) -> None:
        layers = [["node_a"]]
        coords = TapestryHtmlRenderer._assign_coordinates(layers)
        self.assertIn("node_a", coords)
        x, y = coords["node_a"]
        self.assertIsInstance(x, (int, float))
        self.assertIsInstance(y, (int, float))

    def test_two_nodes_same_layer_different_x(self) -> None:
        layers = [["a", "b"]]
        coords = TapestryHtmlRenderer._assign_coordinates(layers)
        self.assertNotEqual(coords["a"][0], coords["b"][0])


class TestTapestryHtmlRendererShort(unittest.TestCase):
    def test_last_segment(self) -> None:
        self.assertEqual(TapestryHtmlRenderer._short("pirn.nodes.MyKnot"), "MyKnot")

    def test_bare_name(self) -> None:
        self.assertEqual(TapestryHtmlRenderer._short("MyKnot"), "MyKnot")


class TestTapestryHtmlRendererTruncate(unittest.TestCase):
    def test_short_string_unchanged(self) -> None:
        self.assertEqual(TapestryHtmlRenderer._truncate("hello", 10), "hello")

    def test_long_string_truncated(self) -> None:
        result = TapestryHtmlRenderer._truncate("a" * 20, 10)
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("…"))


class TestTapestryHtmlRendererRenderSvg(unittest.TestCase):
    def test_empty_nodes_returns_placeholder(self) -> None:
        svg = TapestryHtmlRenderer._render_svg([], [], {})
        self.assertIn("empty run", svg)

    def test_single_node_svg_contains_id(self) -> None:
        nodes = [{
            "id": "my_node",
            "class": "MyKnot",
            "outcome": "ok",
            "duration_ms": 0,
            "output_hash": "",
            "config_hash": "abc",
            "error_record_id": "",
            "skip_reason": "",
            "is_sub_tapestry": False,
        }]
        coords = {"my_node": (0.0, 60.0)}
        svg = TapestryHtmlRenderer._render_svg(nodes, [], coords)
        self.assertIn("<svg", svg)
        self.assertIn("my_node", svg)


class TestHtmlForTapestryWrapper(unittest.TestCase):
    def test_produces_html_document(self) -> None:
        tapestry = _make_tapestry()
        result = html_for_tapestry(tapestry)
        self.assertIn("<!doctype html", result.lower())

    def test_custom_title_in_output(self) -> None:
        tapestry = _make_tapestry()
        result = html_for_tapestry(tapestry, title="My Custom Title")
        self.assertIn("My Custom Title", result)
