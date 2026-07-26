"""``SystemPromptLayer`` — one labelled slice of a composed system prompt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SystemPromptLayer(PirnOpaqueValue):
    """A single layer contributing to a composed system prompt.

    Attributes
    ----------
    kind:
        The layer's role. The canonical kinds and their fixed composition order
        are owned by
        :class:`~pirn_agents.prompt.system_prompt_kind.SystemPromptKind`; any
        other kind is a *custom* layer that composes after the canonical ones in
        first-seen order. Kept a plain ``str`` so custom kinds stay free-form —
        only non-emptiness is validated.
    content:
        The layer body. Empty/whitespace-only content is skipped by the
        composer rather than emitting a blank section.
    title:
        Optional heading rendered above the content (e.g. ``"# Tools"``).
    """

    kind: str
    content: str
    title: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise TypeError("SystemPromptLayer: kind must be a non-empty str")
        if not isinstance(self.content, str):
            raise TypeError(
                f"SystemPromptLayer: content must be a str, got {type(self.content).__name__}"
            )
        if self.title is not None and not isinstance(self.title, str):
            raise TypeError("SystemPromptLayer: title must be a str or None")

    def is_empty(self) -> bool:
        """Return whether this layer has no renderable content."""
        return not self.content.strip()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "content": self.content, "title": self.title}
