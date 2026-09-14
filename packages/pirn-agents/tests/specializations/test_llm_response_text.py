"""Tests for :class:`LlmResponseText` — the one chat-completion text normaliser."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from pirn_agents.specializations.llm_response_text import LlmResponseText


class TestLlmResponseText:
    """Every shape the provider-neutral ``LLMProvider.chat`` return may take."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("plain", "plain"),
            ({"content": "hello"}, "hello"),
            ({"content": [{"text": "hi"}]}, "hi"),
            ({"content": ["first", "second"]}, "first"),
            ({"text": "top-level"}, "top-level"),
            (MappingProxyType({"content": "read-only"}), "read-only"),
        ],
    )
    def test_extracts_known_shapes(self, raw: object, expected: str) -> None:
        # Arrange
        extractor = LlmResponseText()

        # Act
        text = extractor.extract(raw)

        # Assert
        assert text == expected

    @pytest.mark.parametrize(
        "raw",
        [{"content": []}, {"content": [{"type": "image"}]}, {"content": 3}, 42, None],
    )
    def test_falls_back_to_str_for_unknown_shapes(self, raw: object) -> None:
        # Arrange
        extractor = LlmResponseText()

        # Act
        text = extractor.extract(raw)

        # Assert
        assert text == str(raw)
