"""``HtmlToTextTool`` — strip HTML markup to plain text, with output caps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.web._text_extractor import _TextExtractor


class HtmlToTextTool(BaseTool):
    """Convert an HTML string to plain text, truncating to protect the context window."""

    def __init__(self, *, max_chars: int = 20_000) -> None:
        """Bind the tool to an output character cap.

        Args:
            max_chars: Maximum characters of extracted text returned; longer text
                is truncated and flagged.

        Raises:
            ValueError: If ``max_chars`` is not positive.
        """
        if max_chars <= 0:
            raise ValueError(f"html_to_text: max_chars must be positive, got {max_chars}")
        self._max_chars = max_chars

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"html_to_text"``."""
        return "html_to_text"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Extract readable plain text from an HTML string, dropping scripts and styles."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``html`` argument."""
        return {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "The HTML markup to convert to plain text.",
                }
            },
            "required": ["html"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Convert the ``html`` argument to text, capped at ``max_chars``.

        Returns:
            ``{"text", "truncated"}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``html`` is missing or not a string.
        """
        self._require_mapping(self.name, arguments)
        html = self._string_argument(self.name, arguments, "html", allow_empty=True)
        extractor = _TextExtractor()
        extractor.feed(html)
        extractor.close()
        text = extractor.text()
        truncated = len(text) > self._max_chars
        return {"text": text[: self._max_chars], "truncated": truncated}
