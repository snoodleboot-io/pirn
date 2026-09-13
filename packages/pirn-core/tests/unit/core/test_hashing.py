from __future__ import annotations

import unittest

import pytest

from pirn.core.hashing import content_hash
from pirn.exceptions.pirn_error import PirnError
from pirn.exceptions.unhashable_value_error import UnhashableValueError


class TestContentHash(unittest.TestCase):
    def test_returns_sha256_prefix(self) -> None:
        h = content_hash(42)
        self.assertTrue(h.startswith("sha256:"))

    def test_digest_length(self) -> None:
        h = content_hash("hello")
        self.assertEqual(len(h), 7 + 64)

    def test_same_value_same_hash(self) -> None:
        self.assertEqual(content_hash(1), content_hash(1))

    def test_different_values_different_hash(self) -> None:
        self.assertNotEqual(content_hash(1), content_hash(2))

    def test_none_hashes(self) -> None:
        h = content_hash(None)
        self.assertTrue(h.startswith("sha256:"))
        self.assertNotIn("unhashable", h)

    def test_bool_hashes(self) -> None:
        self.assertNotEqual(content_hash(True), content_hash(False))

    def test_string_hashes(self) -> None:
        self.assertNotEqual(content_hash("a"), content_hash("b"))

    def test_bytes_hashes(self) -> None:
        h = content_hash(b"\x00\x01")
        self.assertNotIn("unhashable", h)
        self.assertEqual(content_hash(b"\x00\x01"), content_hash(b"\x00\x01"))
        self.assertNotEqual(content_hash(b"\x00"), content_hash(b"\x01"))

    def test_dict_key_order_irrelevant(self) -> None:
        self.assertEqual(content_hash({"a": 1, "b": 2}), content_hash({"b": 2, "a": 1}))

    def test_list_order_preserved(self) -> None:
        self.assertNotEqual(content_hash([1, 2]), content_hash([2, 1]))

    def test_set_order_independent(self) -> None:
        self.assertEqual(content_hash({1, 2, 3}), content_hash({3, 1, 2}))

    def test_frozenset_hashes(self) -> None:
        self.assertEqual(content_hash(frozenset({1, 2})), content_hash(frozenset({2, 1})))

    def test_nested_dict(self) -> None:
        a = content_hash({"x": {"y": 1}})
        b = content_hash({"x": {"y": 1}})
        self.assertEqual(a, b)
        self.assertNotEqual(a, content_hash({"x": {"y": 2}}))

    def test_pydantic_model(self) -> None:
        from pydantic import BaseModel

        class M(BaseModel):
            x: int
            y: str

        m1 = M(x=1, y="a")
        m2 = M(x=1, y="a")
        m3 = M(x=2, y="a")
        self.assertEqual(content_hash(m1), content_hash(m2))
        self.assertNotEqual(content_hash(m1), content_hash(m3))

    def test_opaque_type_returns_unhashable_marker(self) -> None:
        class Opaque:
            pass

        h = content_hash(Opaque())
        self.assertIn("unhashable", h)

    def test_tuple_hashed_as_sequence(self) -> None:
        self.assertEqual(content_hash((1, 2)), content_hash((1, 2)))
        self.assertNotEqual(content_hash((1, 2)), content_hash((2, 1)))

    def test_empty_dict(self) -> None:
        h = content_hash({})
        self.assertNotIn("unhashable", h)

    def test_empty_list(self) -> None:
        h = content_hash([])
        self.assertNotIn("unhashable", h)

    def test_float_hashes(self) -> None:
        self.assertEqual(content_hash(1.5), content_hash(1.5))
        self.assertNotEqual(content_hash(1.5), content_hash(2.5))


class TestContentHashStrict(unittest.TestCase):
    """``strict=True`` — ADR agents-speaks-core WS2 part 2."""

    def test_strict_defaults_to_false_and_is_unchanged(self) -> None:
        class Opaque:
            pass

        h = content_hash(Opaque())
        self.assertIn("unhashable", h)

    def test_strict_true_raises_on_a_top_level_opaque_value(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError) as excinfo:
            content_hash(Widget(), strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_names_the_innermost_type_in_a_dict(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError) as excinfo:
            content_hash({"a": {"b": Widget()}}, strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_names_the_innermost_type_in_a_list(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError) as excinfo:
            content_hash([1, [2, Widget()]], strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_names_the_innermost_type_in_a_set(self) -> None:
        class Widget:
            def __hash__(self) -> int:
                return 1

        with pytest.raises(UnhashableValueError) as excinfo:
            content_hash({Widget()}, strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_does_not_affect_a_hashable_value(self) -> None:
        assert content_hash({"a": 1}, strict=True) == content_hash({"a": 1})

    def test_strict_true_does_not_affect_a_hashable_set(self) -> None:
        assert content_hash({1, 2, 3}, strict=True) == content_hash({1, 2, 3})

    def test_unhashable_value_error_is_a_pirn_error_and_a_type_error(self) -> None:
        class Widget:
            pass

        with pytest.raises(PirnError):
            content_hash(Widget(), strict=True)
        with pytest.raises(TypeError):
            content_hash(Widget(), strict=True)

    def test_unhashable_value_error_message_names_the_type(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError, match="Widget"):
            content_hash(Widget(), strict=True)
