"""``StreamDelta`` — one unified fragment of a streamed chat completion.

Providers stream a completion as a series of small events. A
:class:`StreamDelta` is the single, provider-neutral shape every adapter emits
so downstream code never sees a vendor payload:

* a slice of assistant *content* (``content``),
* and/or an incremental *tool-call* fragment (``tool_call``) in the neutral
  shape consumed by
  :class:`pirn_agents.streaming_tool_call_parser.StreamingToolCallParser`,
* plus terminal metadata when known (``finish_reason``, ``usage``).

Any field may be empty/``None`` on a given delta; a consumer folds the stream
by concatenating ``content``, feeding ``tool_call`` fragments to the parser,
and keeping the last non-``None`` ``finish_reason`` / ``usage``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class StreamDelta(PirnOpaqueValue):
    """A single neutral fragment yielded by ``stream_chat``.

    Attributes
    ----------
    content:
        A slice of assistant text; empty string when this delta carries no
        content (e.g. a pure tool-call fragment).
    tool_call:
        A neutral streaming tool-call delta mapping (``index``/``id``/``name``/
        ``arguments``/optional ``done``) or ``None``.
    finish_reason:
        The terminal reason when the provider signalled completion, else
        ``None``.
    usage:
        A token-usage mapping when the provider reported it (often only on the
        first and/or last event), else ``None``.
    """

    content: str = ""
    tool_call: Mapping[str, Any] | None = None
    finish_reason: str | None = None
    usage: Mapping[str, int] | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tool_call": None if self.tool_call is None else dict(self.tool_call),
            "finish_reason": self.finish_reason,
            "usage": None if self.usage is None else dict(self.usage),
        }
