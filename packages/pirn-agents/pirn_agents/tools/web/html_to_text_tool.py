"""``HtmlToTextTool`` — strip HTML markup to plain text, with output caps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.web._text_extractor import _TextExtractor


class HtmlToTextTool(Tool):
    """Extract readable plain text from an HTML string, dropping scripts and styles."""

    tool_name: ClassVar[str] = "html_to_text"

    def __init__(
        self,
        *,
        html: Knot | str,
        max_chars: Knot | int = 20_000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(html=html, max_chars=max_chars, _config=_config, **kwargs)

    async def process(
        self,
        html: Annotated[str, Field(description="The HTML markup to convert to plain text.")],
        max_chars: int = 20_000,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Convert ``html`` to text, capped at ``max_chars``.

        Args:
            html: The markup to convert; an empty string is allowed.
            max_chars: Maximum characters of extracted text returned; longer
                text is truncated and flagged.

        Returns:
            ``{"text", "truncated"}``.

        Raises:
            ValueError: If ``max_chars`` is not positive.
        """
        if max_chars <= 0:
            raise ValueError(f"html_to_text: max_chars must be positive, got {max_chars}")
        extractor = _TextExtractor()
        extractor.feed(html)
        extractor.close()
        text = extractor.text()
        truncated = len(text) > max_chars
        return {"text": text[:max_chars], "truncated": truncated}
