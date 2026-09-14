"""The full conversational state passed between agent knots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.payload import Payload
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_frame import ConversationFrame


class ConversationPayload(Payload[ConversationFrame, tuple[AgentMessage, ...]]):
    """Conversation history plus its :class:`ConversationFrame` lineage.

    ``ConversationPayload`` is
    ``Payload[ConversationFrame, tuple[AgentMessage, ...]]`` (ADR
    agents-speaks-core WS6b) — ``data`` is the ordered tuple of
    :class:`AgentMessage`, ``metadata`` is the
    :class:`~pirn_agents.types.messaging.conversation_frame.ConversationFrame`
    describing the window (session/turn ids, token count, truncation state,
    and the free-form ``extra`` bag). It replaces ``AgentContext`` (deleted,
    PIR-864).

    Attributes
    ----------
    messages:
        Ordered tuple of :class:`AgentMessage` covering the conversation so
        far (the payload's ``data``).
    extra:
        Mapping for intermediate state shared between knots (parsed
        intents, retrieved memories, partial plans). Defaults to an empty
        dict. Named ``extra`` because :attr:`Payload.metadata` names the frame.
    """

    def __init__(
        self,
        messages: Sequence[AgentMessage] = (),
        *,
        extra: Mapping[str, Any] | None = None,
        session_id: str | None = None,
        turn_id: str | None = None,
        token_count: int = 0,
        truncated: bool = False,
    ) -> None:
        frame = ConversationFrame(
            session_id=session_id,
            turn_id=turn_id,
            token_count=token_count,
            truncated=truncated,
            extra=dict(extra or {}),
        )
        super().__init__(metadata=frame, data=tuple(messages))

    @property
    def frame(self) -> ConversationFrame:
        return self._metadata

    @property
    def messages(self) -> tuple[AgentMessage, ...]:
        return self._data

    @property
    def extra(self) -> Mapping[str, Any]:
        return self._metadata.extra

    def derive(
        self, messages: Sequence[AgentMessage], **frame_overrides: Any
    ) -> ConversationPayload:
        """Build a new :class:`ConversationPayload` derived from this one.

        Inherits every :class:`ConversationFrame` field from this payload
        (``session_id``, ``turn_id``, ``token_count``, ``truncated``,
        ``extra``) and pairs them with the new ``messages``. Any frame
        field may be overridden via ``frame_overrides``.

        Args:
            messages: The new message tuple to carry in the derived payload.
            **frame_overrides: Overrides for any :class:`ConversationFrame`
                field.

        Returns:
            A new ``ConversationPayload`` with the derived frame and
            ``messages``.
        """
        fields: dict[str, Any] = {
            "session_id": self.frame.session_id,
            "turn_id": self.frame.turn_id,
            "token_count": self.frame.token_count,
            "truncated": self.frame.truncated,
            "extra": dict(self.frame.extra),
        }
        fields.update(frame_overrides)
        return ConversationPayload(messages, **fields)

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["messages"] = self._audit_all(self.messages)
        return audit

    def __repr__(self) -> str:
        return f"{type(self).__name__}(messages={self.messages!r}, frame={self._metadata!r})"
