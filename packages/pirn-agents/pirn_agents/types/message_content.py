"""``MessageContent`` — a normalized, typed sequence of content blocks (F15-S1).

The typed replacement for a message's plain-string body: an ordered tuple of
:class:`~pirn_agents.types.content_block.ContentBlock`. Backward compatibility is
the whole point of :meth:`coerce` — a plain ``str`` normalizes to a single
:class:`~pirn_agents.types.text_block.TextBlock`, so every existing text-only
caller keeps working while multimodal callers pass real blocks. :attr:`text`
gives the flat text projection so any consumer can still read a message as a
string.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.text_block import TextBlock


@dataclass(frozen=True)
class MessageContent(PirnOpaqueValue):
    """An ordered, typed sequence of content blocks.

    Attributes
    ----------
    blocks:
        The ordered content blocks composing the message body.
    """

    blocks: tuple[ContentBlock, ...]

    def __post_init__(self) -> None:
        """Validate that every item is a :class:`ContentBlock`.

        Raises:
            TypeError: If ``blocks`` is not a sequence of :class:`ContentBlock`.
        """
        if not isinstance(self.blocks, tuple):
            raise TypeError("MessageContent: blocks must be a tuple of ContentBlock")
        for block in self.blocks:
            if not isinstance(block, ContentBlock):
                raise TypeError(
                    "MessageContent: every block must be a ContentBlock, "
                    f"got {type(block).__name__}"
                )

    @classmethod
    def coerce(
        cls,
        value: str | ContentBlock | Sequence[ContentBlock] | MessageContent,
    ) -> MessageContent:
        """Normalize ``value`` into a :class:`MessageContent`.

        A plain ``str`` becomes a single :class:`TextBlock` (the backward-
        compatible path); a lone :class:`ContentBlock` is wrapped; a sequence of
        blocks is captured as-is; an existing :class:`MessageContent` is returned
        unchanged.

        Raises:
            TypeError: If ``value`` is none of the accepted shapes, or a sequence
                item is not a :class:`ContentBlock`.
        """
        if isinstance(value, MessageContent):
            return value
        if isinstance(value, str):
            return cls(blocks=(TextBlock(text=value),))
        if isinstance(value, ContentBlock):
            return cls(blocks=(value,))
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return cls(blocks=tuple(value))
        raise TypeError(
            "MessageContent.coerce: value must be a str, ContentBlock, sequence "
            f"of ContentBlock, or MessageContent; got {type(value).__name__}"
        )

    @property
    def text(self) -> str:
        """Return the flat text projection across all blocks."""
        return "".join(block.as_text for block in self.blocks)

    def __iter__(self) -> Iterator[ContentBlock]:
        """Iterate the content blocks in order."""
        return iter(self.blocks)

    def __len__(self) -> int:
        """Return the number of content blocks."""
        return len(self.blocks)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"blocks": [block._pirn_audit_dict() for block in self.blocks]}
