"""``ToolResultBlock`` — the tool-result variant of the content-block union (F15-S1).

A tool result can appear *inline* in a message body (correlated to the call it
answers) and can itself carry multimodal payload — e.g. a data tool returning a
chart image. This block wraps the answering :attr:`call_id` and the nested
sequence of :class:`~pirn_agents.types.content_block.ContentBlock` it produced.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.message_content import MessageContent
from pirn_agents.types.text_block import TextBlock
from pirn_agents.types.tool_result import ToolResult


@dataclass(frozen=True)
class ToolResultBlock(ContentBlock):
    """An embedded tool result carrying its own nested content blocks.

    Attributes
    ----------
    call_id:
        Identifier of the tool call this result answers.
    blocks:
        The nested content blocks the tool produced (text and/or media).
    """

    call_id: str
    blocks: tuple[ContentBlock, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate the call id and that every nested item is a content block.

        Raises:
            TypeError: If ``call_id`` is not a string, ``blocks`` is not a
                sequence, or any nested item is not a :class:`ContentBlock`.
        """
        if not isinstance(self.call_id, str):
            raise TypeError(
                f"ToolResultBlock: call_id must be a str, got {type(self.call_id).__name__}"
            )
        if not isinstance(self.blocks, Sequence) or isinstance(self.blocks, (str, bytes)):
            raise TypeError("ToolResultBlock: blocks must be a sequence of ContentBlock")
        for block in self.blocks:
            if not isinstance(block, ContentBlock):
                raise TypeError(
                    "ToolResultBlock: every nested block must be a ContentBlock, "
                    f"got {type(block).__name__}"
                )

    @classmethod
    def from_tool_result(cls, result: ToolResult) -> ToolResultBlock:
        """Project an F1 :class:`ToolResult` into a tool-result content block.

        The tool's raw :attr:`~pirn_agents.types.tool_result.ToolResult.result`
        is normalized into nested content blocks: an existing
        :class:`MessageContent` contributes its blocks, a lone
        :class:`ContentBlock` (or a sequence of them) is carried through, and any
        other value degrades to a single
        :class:`~pirn_agents.types.text_block.TextBlock` of its string form (an
        errored result uses its error text). This is the multimodal path for
        tool outputs — a tool returning an image block surfaces it inline.

        Raises:
            TypeError: If ``result`` is not a :class:`ToolResult`.
        """
        if not isinstance(result, ToolResult):
            raise TypeError(
                "ToolResultBlock.from_tool_result: result must be a ToolResult, "
                f"got {type(result).__name__}"
            )
        payload = result.result
        if isinstance(payload, MessageContent):
            nested: tuple[ContentBlock, ...] = payload.blocks
        elif isinstance(payload, ContentBlock):
            nested = (payload,)
        elif (
            isinstance(payload, Sequence)
            and not isinstance(payload, (str, bytes))
            and all(isinstance(item, ContentBlock) for item in payload)
        ):
            nested = tuple(payload)
        else:
            if result.error is not None:
                text = result.error
            elif payload is None:
                text = ""
            else:
                text = str(payload)
            nested = (TextBlock(text=text),)
        return cls(call_id=result.call_id, blocks=nested)

    @property
    def modality(self) -> str:
        """Return the neutral modality tag ``"tool_result"``."""
        return "tool_result"

    @property
    def as_text(self) -> str:
        """Return the concatenated text projection of the nested blocks."""
        return "".join(block.as_text for block in self.blocks)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "modality": "tool_result",
            "call_id": self.call_id,
            "blocks": [block._pirn_audit_dict() for block in self.blocks],
        }
