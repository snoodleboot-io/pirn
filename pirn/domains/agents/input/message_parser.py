"""``MessageParser`` — coerce raw input into a tuple of :class:`AgentMessage`.

Accepts plain strings, mappings, :class:`AgentMessage` instances, or
sequences thereof. Anything else fails fast at process time so callers
cannot smuggle untyped state past the input boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_message import AgentMessage


class MessageParser(Knot):
    """Parses raw input into a non-empty ``tuple[AgentMessage, ...]``."""

    def __init__(
        self,
        *,
        raw_input: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(raw_input=raw_input, _config=_config, **kwargs)

    async def process(
        self,
        raw_input: Any,
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        items = self._coerce_to_iterable(raw_input)
        parsed = tuple(self._coerce_one(index, item) for index, item in enumerate(items))
        if not parsed:
            raise ValueError(
                "MessageParser: raw_input produced zero messages; "
                "input must be non-empty"
            )
        return parsed

    def _coerce_to_iterable(self, raw_input: Any) -> Sequence[Any]:
        if isinstance(raw_input, AgentMessage):
            return (raw_input,)
        if isinstance(raw_input, str):
            if not raw_input:
                raise ValueError(
                    "MessageParser: raw_input string must be non-empty"
                )
            return (raw_input,)
        if isinstance(raw_input, Mapping):
            return (raw_input,)
        if isinstance(raw_input, Sequence) and not isinstance(raw_input, (str, bytes)):
            return tuple(raw_input)
        raise TypeError(
            "MessageParser: raw_input must be a str, Mapping, AgentMessage, "
            f"or sequence thereof; got {type(raw_input).__name__}"
        )

    def _coerce_one(self, index: int, item: Any) -> AgentMessage:
        if isinstance(item, AgentMessage):
            return item
        if isinstance(item, str):
            if not item:
                raise ValueError(
                    f"MessageParser: item[{index}] string must be non-empty"
                )
            return AgentMessage(role="user", content=item)
        if isinstance(item, Mapping):
            role = item.get("role", "user")
            if not isinstance(role, str) or not role:
                raise ValueError(
                    f"MessageParser: item[{index}].role must be a non-empty string, "
                    f"got {role!r}"
                )
            content = item.get("content")
            if not isinstance(content, str):
                raise ValueError(
                    f"MessageParser: item[{index}].content must be a string, "
                    f"got {type(content).__name__}"
                )
            return AgentMessage(
                role=role,
                content=content,
                name=item.get("name"),
                tool_call_id=item.get("tool_call_id"),
            )
        raise TypeError(
            f"MessageParser: item[{index}] must be a str, Mapping, or "
            f"AgentMessage; got {type(item).__name__}"
        )
