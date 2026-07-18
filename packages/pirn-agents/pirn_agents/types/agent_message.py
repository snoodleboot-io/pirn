"""A single conversational turn flowing through an agent pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.text_block import TextBlock


@dataclass(frozen=True)
class AgentMessage(PirnOpaqueValue):
    """One message within an agent conversation.

    The body is available two ways that always agree: :attr:`content` is the
    plain-text projection (backward-compatible — every existing text-only caller
    keeps working) and :attr:`blocks` is the optional typed multimodal sequence.
    When ``blocks`` is ``None`` the message is text-only and
    :attr:`content_blocks` synthesises a single
    :class:`~pirn_agents.types.text_block.TextBlock` from :attr:`content`; when
    ``blocks`` is set it is the authoritative body and :attr:`content` holds its
    text projection. Build a multimodal message with :meth:`from_blocks`.

    Attributes
    ----------
    role:
        Who produced the message (e.g. ``"user"``, ``"assistant"``,
        ``"system"``, ``"tool"``).
    content:
        The message body as plain text (the text projection when
        :attr:`blocks` is set).
    name:
        Optional name of the tool or sub-agent that produced the
        message.
    tool_call_id:
        Set when ``role == "tool"`` to correlate the message with the
        tool invocation it answers.
    created_at:
        UTC instant the message was produced.
    blocks:
        Optional typed multimodal content sequence; ``None`` for a text-only
        message.
    """

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    blocks: tuple[ContentBlock, ...] | None = None

    def __post_init__(self) -> None:
        """Validate that every supplied block is a :class:`ContentBlock`.

        Raises:
            TypeError: If ``blocks`` is set but is not a sequence of
                :class:`ContentBlock`.
        """
        if self.blocks is None:
            return
        if not isinstance(self.blocks, Sequence) or isinstance(self.blocks, (str, bytes)):
            raise TypeError("AgentMessage: blocks must be a sequence of ContentBlock or None")
        for block in self.blocks:
            if not isinstance(block, ContentBlock):
                raise TypeError(
                    f"AgentMessage: every block must be a ContentBlock, got {type(block).__name__}"
                )

    @classmethod
    def from_blocks(
        cls,
        *,
        role: str,
        blocks: Sequence[ContentBlock],
        name: str | None = None,
        tool_call_id: str | None = None,
        created_at: datetime | None = None,
    ) -> AgentMessage:
        """Build a multimodal message from ``blocks``.

        The text projection of the blocks is stored in :attr:`content` so a
        text-only consumer still reads a coherent string.

        Raises:
            TypeError: If any item in ``blocks`` is not a :class:`ContentBlock`.
        """
        captured = tuple(blocks)
        for block in captured:
            if not isinstance(block, ContentBlock):
                raise TypeError(
                    "AgentMessage.from_blocks: every block must be a ContentBlock, "
                    f"got {type(block).__name__}"
                )
        text = "".join(block.as_text for block in captured)
        kwargs: dict[str, Any] = {
            "role": role,
            "content": text,
            "name": name,
            "tool_call_id": tool_call_id,
            "blocks": captured,
        }
        if created_at is not None:
            kwargs["created_at"] = created_at
        return cls(**kwargs)

    @property
    def content_blocks(self) -> tuple[ContentBlock, ...]:
        """Return the typed content blocks for this message.

        When :attr:`blocks` is set it is returned; otherwise the plain
        :attr:`content` is coerced to a single :class:`TextBlock`, so every
        message exposes a uniform block view regardless of how it was built.
        """
        if self.blocks is not None:
            return self.blocks
        return (TextBlock(text=self.content),)

    @property
    def text(self) -> str:
        """Return the plain-text projection of the message body.

        Identical to :attr:`content`; provided so callers can read ``.text`` on
        a message the same way they read it on a block.
        """
        if self.blocks is None:
            return self.content
        return "".join(block.as_text for block in self.blocks)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "created_at": self.created_at.isoformat(),
            "blocks": (
                None if self.blocks is None else [block._pirn_audit_dict() for block in self.blocks]
            ),
        }
