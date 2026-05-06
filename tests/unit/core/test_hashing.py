from __future__ import annotations

import unittest

from pirn.core.hashing import content_hash


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
