"""Unit tests for the :func:`content_address` keyer."""

from __future__ import annotations

from pirn_agents.caching.content_address import content_address


class TestContentAddress:
    def test_identical_payloads_same_key(self) -> None:
        assert content_address({"q": "dicom"}) == content_address({"q": "dicom"})

    def test_key_is_order_independent_for_mappings(self) -> None:
        assert content_address({"a": 1, "b": 2}) == content_address({"b": 2, "a": 1})

    def test_different_payloads_differ(self) -> None:
        assert content_address({"q": "a"}) != content_address({"q": "b"})

    def test_non_json_value_does_not_raise(self) -> None:
        key = content_address({"obj": object()})
        assert isinstance(key, str) and len(key) == 64

    def test_returns_hex_sha256(self) -> None:
        key = content_address("x")
        assert len(key) == 64
        int(key, 16)  # parses as hex
