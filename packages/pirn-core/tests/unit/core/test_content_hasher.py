from __future__ import annotations

import unittest

import pytest

from pirn.core.content_hasher import ContentHasher
from pirn.exceptions.pirn_error import PirnError
from pirn.exceptions.unhashable_value_error import UnhashableValueError


class TestContentHash(unittest.TestCase):
    def test_returns_sha256_prefix(self) -> None:
        h = ContentHasher.hash(42)
        self.assertTrue(h.startswith("sha256:"))

    def test_digest_length(self) -> None:
        h = ContentHasher.hash("hello")
        self.assertEqual(len(h), 7 + 64)

    def test_same_value_same_hash(self) -> None:
        self.assertEqual(ContentHasher.hash(1), ContentHasher.hash(1))

    def test_different_values_different_hash(self) -> None:
        self.assertNotEqual(ContentHasher.hash(1), ContentHasher.hash(2))

    def test_none_hashes(self) -> None:
        h = ContentHasher.hash(None)
        self.assertTrue(h.startswith("sha256:"))
        self.assertNotIn("unhashable", h)

    def test_bool_hashes(self) -> None:
        self.assertNotEqual(ContentHasher.hash(True), ContentHasher.hash(False))

    def test_string_hashes(self) -> None:
        self.assertNotEqual(ContentHasher.hash("a"), ContentHasher.hash("b"))

    def test_bytes_hashes(self) -> None:
        h = ContentHasher.hash(b"\x00\x01")
        self.assertNotIn("unhashable", h)
        self.assertEqual(ContentHasher.hash(b"\x00\x01"), ContentHasher.hash(b"\x00\x01"))
        self.assertNotEqual(ContentHasher.hash(b"\x00"), ContentHasher.hash(b"\x01"))

    def test_dict_key_order_irrelevant(self) -> None:
        self.assertEqual(ContentHasher.hash({"a": 1, "b": 2}), ContentHasher.hash({"b": 2, "a": 1}))

    def test_list_order_preserved(self) -> None:
        self.assertNotEqual(ContentHasher.hash([1, 2]), ContentHasher.hash([2, 1]))

    def test_set_order_independent(self) -> None:
        self.assertEqual(ContentHasher.hash({1, 2, 3}), ContentHasher.hash({3, 1, 2}))

    def test_frozenset_hashes(self) -> None:
        self.assertEqual(
            ContentHasher.hash(frozenset({1, 2})), ContentHasher.hash(frozenset({2, 1}))
        )

    def test_nested_dict(self) -> None:
        a = ContentHasher.hash({"x": {"y": 1}})
        b = ContentHasher.hash({"x": {"y": 1}})
        self.assertEqual(a, b)
        self.assertNotEqual(a, ContentHasher.hash({"x": {"y": 2}}))

    def test_pydantic_model(self) -> None:
        from pydantic import BaseModel

        class M(BaseModel):
            x: int
            y: str

        m1 = M(x=1, y="a")
        m2 = M(x=1, y="a")
        m3 = M(x=2, y="a")
        self.assertEqual(ContentHasher.hash(m1), ContentHasher.hash(m2))
        self.assertNotEqual(ContentHasher.hash(m1), ContentHasher.hash(m3))

    def test_opaque_type_returns_unhashable_marker(self) -> None:
        class Opaque:
            pass

        h = ContentHasher.hash(Opaque())
        self.assertIn("unhashable", h)

    def test_canonicalisation_bail_out_is_a_pirn_error(self) -> None:
        class Opaque:
            pass

        with pytest.raises(PirnError):
            ContentHasher._canonicalise(Opaque())

    def test_tuple_hashed_as_sequence(self) -> None:
        self.assertEqual(ContentHasher.hash((1, 2)), ContentHasher.hash((1, 2)))
        self.assertNotEqual(ContentHasher.hash((1, 2)), ContentHasher.hash((2, 1)))

    def test_empty_dict(self) -> None:
        h = ContentHasher.hash({})
        self.assertNotIn("unhashable", h)

    def test_empty_list(self) -> None:
        h = ContentHasher.hash([])
        self.assertNotIn("unhashable", h)

    def test_float_hashes(self) -> None:
        self.assertEqual(ContentHasher.hash(1.5), ContentHasher.hash(1.5))
        self.assertNotEqual(ContentHasher.hash(1.5), ContentHasher.hash(2.5))


class TestContentHashStrict(unittest.TestCase):
    """``strict=True`` — ADR agents-speaks-core WS2 part 2."""

    def test_strict_defaults_to_false_and_is_unchanged(self) -> None:
        class Opaque:
            pass

        h = ContentHasher.hash(Opaque())
        self.assertIn("unhashable", h)

    def test_strict_true_raises_on_a_top_level_opaque_value(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError) as excinfo:
            ContentHasher.hash(Widget(), strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_names_the_innermost_type_in_a_dict(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError) as excinfo:
            ContentHasher.hash({"a": {"b": Widget()}}, strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_names_the_innermost_type_in_a_list(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError) as excinfo:
            ContentHasher.hash([1, [2, Widget()]], strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_names_the_innermost_type_in_a_set(self) -> None:
        class Widget:
            def __hash__(self) -> int:
                return 1

        with pytest.raises(UnhashableValueError) as excinfo:
            ContentHasher.hash({Widget()}, strict=True)
        assert excinfo.value.type_name == "Widget"

    def test_strict_true_does_not_affect_a_hashable_value(self) -> None:
        assert ContentHasher.hash({"a": 1}, strict=True) == ContentHasher.hash({"a": 1})

    def test_strict_true_does_not_affect_a_hashable_set(self) -> None:
        assert ContentHasher.hash({1, 2, 3}, strict=True) == ContentHasher.hash({1, 2, 3})

    def test_unhashable_value_error_is_a_pirn_error_and_a_type_error(self) -> None:
        class Widget:
            pass

        with pytest.raises(PirnError):
            ContentHasher.hash(Widget(), strict=True)
        with pytest.raises(TypeError):
            ContentHasher.hash(Widget(), strict=True)

    def test_unhashable_value_error_message_names_the_type(self) -> None:
        class Widget:
            pass

        with pytest.raises(UnhashableValueError, match="Widget"):
            ContentHasher.hash(Widget(), strict=True)
