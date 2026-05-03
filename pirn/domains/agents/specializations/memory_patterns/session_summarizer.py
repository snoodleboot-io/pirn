"""``SessionSummarizer`` — compress conversation history when it exceeds a token threshold.

Counts approximate tokens in the conversation history. When the total
exceeds ``token_threshold``, calls the LLM to produce a condensed summary
and returns a replacement message list. Otherwise returns the messages
unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_message import AgentMessage


class SessionSummarizer(Knot):
    """Compress messages via LLM when they exceed the token threshold."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        llm: LLMProvider,
        _config: KnotConfig,
        token_threshold: int = 2000,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "SessionSummarizer: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(token_threshold, int) or token_threshold <= 0:
            raise ValueError(
                "SessionSummarizer: token_threshold must be a positive int, "
                f"got {token_threshold!r}"
            )
        self._llm = llm
        self._token_threshold = token_threshold
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> list[AgentMessage]:
        """Compress conversation history if it exceeds the token threshold.

        Args:
            messages: The full conversation history to evaluate and possibly compress.

        Returns:
            The original message list if under threshold, or a compressed list with
            a summary message prepended and only the most recent message appended.

        Raises:
            TypeError: If any element of messages is not an AgentMessage.
        """
        message_list = list(messages)
        for index, msg in enumerate(message_list):
            if not isinstance(msg, AgentMessage):
                raise TypeError(
                    f"SessionSummarizer: messages[{index}] must be an "
                    f"AgentMessage, got {type(msg).__name__}"
                )
        total_tokens = sum(
            len(msg.content.split()) for msg in message_list
        )
        if total_tokens <= self._token_threshold:
            return message_list

        rendered = "\n".join(
            f"{m.role}: {m.content}" for m in message_list
        )
        summary_prompt = (
            "Summarize the following conversation concisely, preserving "
            "all key facts, decisions, and context needed for the agent "
            "to continue.\n\n"
            f"{rendered}"
        )
        raw = await self._llm.chat([{"role": "user", "content": summary_prompt}])
        summary_text = self._extract_text(raw)
        summary_msg = AgentMessage(role="system", content=f"[Summary] {summary_text}")
        if message_list:
            return [summary_msg, message_list[-1]]
        return [summary_msg]

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
