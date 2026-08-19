"""Unit tests for the :func:`content_address` keyer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from pirn_agents.caching.content_address import content_address
from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache


class _Request:
    """A live request object with no content-derived ``__repr__``.

    The exact shape behind PIR-785: application objects routinely reach a cache
    without defining ``__repr__``, so ``object.__repr__`` supplies one built
    from the instance's memory address. Its *content* — ``query`` — never
    appears in the repr at all.
    """

    def __init__(self, query: str) -> None:
        self.query = query


class TestContentAddress:
    def test_identical_payloads_same_key(self) -> None:
        assert content_address({"q": "dicom"}) == content_address({"q": "dicom"})

    def test_key_is_order_independent_for_mappings(self) -> None:
        assert content_address({"a": 1, "b": 2}) == content_address({"b": 2, "a": 1})

    def test_different_payloads_differ(self) -> None:
        assert content_address({"q": "a"}) != content_address({"q": "b"})

    def test_non_json_value_raises(self) -> None:
        # Inverted by PIR-785. This previously asserted the keyer "does not
        # raise" on a live object, which is what made the collision below
        # possible: a value JSON cannot represent has no content-derived key,
        # so producing one anyway means producing a wrong one.
        with pytest.raises(TypeError):
            content_address({"obj": object()})

    def test_the_raise_names_the_offending_type(self) -> None:
        with pytest.raises(TypeError, match="_Request"):
            content_address({"obj": _Request("q")})

    def test_returns_hex_sha256(self) -> None:
        key = content_address("x")
        assert len(key) == 64
        int(key, 16)  # parses as hex


class TestContentAddressDoesNotCollide:
    """PIR-785: distinct payloads must never share a cache key.

    A shared key is not a performance bug — ``ResultCache.get_or_compute``
    returns the *previous* request's value for the current request, which is a
    silent wrong answer with no error anywhere.
    """

    def test_distinct_opaque_payloads_never_share_a_key(self) -> None:
        # Pre-fix this produced 17 distinct keys for 200 distinct queries:
        # `default=repr` keyed on the instance's memory address, and CPython
        # hands the freed address straight back to the next allocation.
        keys: list[str] = []
        for index in range(200):
            try:
                keys.append(content_address({"request": _Request(f"query-{index}")}))
            except TypeError:
                continue  # refused outright, so it cannot collide
        assert len(keys) == len(set(keys)), (
            "Two distinct payloads produced the same content address. Any cache "
            "keyed by it will serve one request's value in answer to another."
        )

    def test_opaque_payloads_are_refused_rather_than_mis_keyed(self) -> None:
        # Pins the mechanism the test above relies on, so that it cannot start
        # passing vacuously for some other reason.
        with pytest.raises(TypeError):
            content_address({"request": _Request("query-0")})

    def test_two_live_objects_do_not_share_a_key(self) -> None:
        # Both held alive at once, so no address reuse is involved: this fails
        # pre-fix only if the reprs happen to match, and passes post-fix
        # because neither is encodable at all.
        first = _Request("alpha")
        second = _Request("beta")
        keys: list[str] = []
        for request in (first, second):
            try:
                keys.append(content_address({"request": request}))
            except TypeError:
                continue
        assert len(keys) == len(set(keys))

    async def test_cache_does_not_answer_one_request_with_anothers_value(self) -> None:
        # The user-visible defect, end to end. Pre-fix the second call returned
        # "answer for alpha"; post-fix the mis-keying is impossible because the
        # payload is refused.
        cache = InMemoryResultCache()
        answers: list[str] = []
        for query in ("alpha", "beta"):
            try:
                answers.append(
                    await cache.get_or_compute(
                        {"request": _Request(query)},
                        _make_answer(query),
                    )
                )
            except TypeError:
                continue
        assert len(answers) == len(set(answers)), (
            "The cache served a stale value: two distinct requests collapsed onto one key."
        )


def _make_answer(query: str) -> Callable[[], Awaitable[str]]:
    """Return an async factory yielding the answer for ``query``."""

    async def compute() -> str:
        return f"answer for {query}"

    return compute
