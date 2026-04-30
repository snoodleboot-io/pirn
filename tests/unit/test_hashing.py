"""Content-addressed hashing tests."""

from __future__ import annotations

from pydantic import BaseModel

from pirn.core.hashing import content_hash


def test_primitives_stable():
    assert content_hash(5) == content_hash(5)
    assert content_hash("hello") == content_hash("hello")
    assert content_hash(None) == content_hash(None)
    assert content_hash(True) == content_hash(True)


def test_primitives_distinct():
    assert content_hash(5) != content_hash(5.0) or content_hash(5) != content_hash("5")
    assert content_hash(True) != content_hash(1)
    assert content_hash(None) != content_hash(0)


def test_dict_ordering_doesnt_matter():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert content_hash(a) == content_hash(b)


def test_list_ordering_matters():
    assert content_hash([1, 2, 3]) != content_hash([3, 2, 1])


def test_set_ordering_doesnt_matter():
    assert content_hash({1, 2, 3}) == content_hash({3, 2, 1})


def test_pydantic_model_stable():
    class M(BaseModel):
        x: int
        y: str

    assert content_hash(M(x=1, y="a")) == content_hash(M(x=1, y="a"))
    assert content_hash(M(x=1, y="a")) != content_hash(M(x=2, y="a"))


def test_bytes_stable():
    assert content_hash(b"hello") == content_hash(b"hello")
    assert content_hash(b"hello") != content_hash("hello")


def test_nested_structures():
    a = {"users": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]}
    b = {"users": [{"name": "alice", "id": 1}, {"id": 2, "name": "bob"}]}
    assert content_hash(a) == content_hash(b)


def test_hash_format():
    h = content_hash(42)
    assert h.startswith("sha256:")
    assert len(h) == 7 + 64  # "sha256:" + 64 hex chars


def test_unhashable_returns_marker():
    class Opaque:
        pass

    h = content_hash(Opaque())
    assert "unhashable" in h
