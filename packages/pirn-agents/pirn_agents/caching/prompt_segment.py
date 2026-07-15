"""``PromptSegment`` — one labelled piece of a prompt, marked stable or variable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class PromptSegment(PirnOpaqueValue):
    """A single prompt fragment tagged by how often its content changes.

    Attributes
    ----------
    kind:
        The fragment's role (e.g. ``"system"``, ``"tools"``, ``"user"``), used
        for observability and by callers to decide stability.
    content:
        The fragment text.
    stable:
        Whether this fragment is shared/unchanging across calls (system prompt,
        tool schemas). Stable fragments are hoisted into the cacheable prefix by
        :class:`~pirn_agents.caching.prompt_prefix_orderer.PromptPrefixOrderer`;
        variable fragments (the user turn, retrieved context) follow.
    """

    kind: str
    content: str
    stable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise TypeError("PromptSegment: kind must be a non-empty str")
        if not isinstance(self.content, str):
            raise TypeError(
                f"PromptSegment: content must be a str, got {type(self.content).__name__}"
            )
        if not isinstance(self.stable, bool):
            raise TypeError("PromptSegment: stable must be a bool")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "content": self.content, "stable": self.stable}
