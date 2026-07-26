"""``TextBlockHandler`` — handle ``{"type": "text", "text": "..."}`` blocks.

Contributes the block's ``text`` fragment to the parsed response content. A
block whose ``type`` is ``"text"`` but whose ``text`` is not a string is left
unrecognised (``None``), matching the original permissive parser behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.generation.block_contribution import BlockContribution
from pirn_agents.generation.content_block_handler import ContentBlockHandler


class TextBlockHandler(ContentBlockHandler):
    """Contribute the text fragment of a ``text`` content block."""

    def try_handle(self, block: Mapping[str, Any]) -> BlockContribution | None:
        """Return the text contribution when ``block`` is a text block."""
        if block.get("type") != "text":
            return None
        text = block.get("text")
        if not isinstance(text, str):
            return None
        return BlockContribution(text=text)
