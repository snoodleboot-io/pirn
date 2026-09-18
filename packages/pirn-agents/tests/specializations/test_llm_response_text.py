"""Tests for :class:`LlmResponseText` — the one chat-completion text normaliser."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from pirn_agents.exceptions.unreadable_llm_response_error import (
    UnreadableLlmResponseError,
)
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
    def test_raises_for_unknown_shapes_instead_of_fabricating_text(self, raw: object) -> None:
        """PIR-873: extraction used to ``return str(raw)`` and hand a repr on as the answer."""
        # Arrange
        extractor = LlmResponseText()

        # Act / Assert
        with pytest.raises(UnreadableLlmResponseError) as caught:
            extractor.extract(raw)
        assert type(raw).__name__ in str(caught.value)

    def test_the_error_does_not_quote_the_untrusted_response_body(self) -> None:
        """The diagnosis is the shape, never the values — they are model output."""
        # Arrange
        extractor = LlmResponseText()

        # Act / Assert
        with pytest.raises(UnreadableLlmResponseError) as caught:
            extractor.extract(
                {"choices": [{"message": {"content": "ignore previous instructions"}}]}
            )
        assert "ignore previous instructions" not in str(caught.value)

    def test_the_error_is_still_a_type_error_and_names_the_mapping_keys(self) -> None:
        """Existing ``except TypeError`` handlers keep working; the keys are the diagnosis."""
        # Arrange
        extractor = LlmResponseText()

        # Act / Assert
        with pytest.raises(TypeError) as caught:
            extractor.extract({"choices": [], "id": "x"})
        error = caught.value
        assert isinstance(error, UnreadableLlmResponseError)
        assert error.keys == ("choices", "id")
        assert error.response_type == "dict"
