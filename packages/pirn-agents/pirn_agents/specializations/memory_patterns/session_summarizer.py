"""``SessionSummarizer`` — compress conversation history when it exceeds a token threshold.

Counts approximate tokens in the conversation history. When the total
exceeds ``token_threshold``, calls the LLM to produce a condensed summary
and returns a replacement message list. Otherwise returns the messages
unchanged.

Algorithm
---------
1. Validate inputs.
2. Count approximate tokens as the sum of word-count per message.
3. If total <= token_threshold, return messages unchanged.
4. Otherwise call LLM with a summarization prompt.
5. Return ``[summary_message, last_original_message]``.

Math
----
``total_tokens = sum(len(msg.content.split()) for msg in messages)``

References
----------
None.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.types.agent_message import AgentMessage


class SessionSummarizer(Knot):
    """Compress messages via LLM when they exceed the token threshold."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        llm: Knot | LLMProvider,
        token_threshold: Knot | int = 2000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            llm=llm,
            token_threshold=token_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        llm: LLMProvider,
        token_threshold: int = 2000,
        **_: Any,
    ) -> list[AgentMessage]:
        """Compress conversation history if it exceeds the token threshold.

        Args:
            messages: The full conversation history to evaluate and possibly compress.
            llm: The LLMProvider used to produce the summary.
            token_threshold: Positive int; only compress when token count exceeds this value.

        Returns:
            The original message list if under threshold, or a compressed list with
            a summary message prepended and only the most recent message appended.

        Raises:
            TypeError: If llm is not an LLMProvider or any message is not an AgentMessage.
            ValueError: If token_threshold is not a positive int.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SessionSummarizer: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(token_threshold, int) or token_threshold <= 0:
            raise ValueError(
                "SessionSummarizer: token_threshold must be a positive int, "
                f"got {token_threshold!r}"
            )
        message_list = list(messages)
        for index, msg in enumerate(message_list):
            if not isinstance(msg, AgentMessage):
                raise TypeError(
                    f"SessionSummarizer: messages[{index}] must be an "
                    f"AgentMessage, got {type(msg).__name__}"
                )
        total_tokens = sum(len(msg.content.split()) for msg in message_list)
        if total_tokens <= token_threshold:
            return message_list

        rendered = "\n".join(f"{m.role}: {m.content}" for m in message_list)
        summary_prompt = (
            "Summarize the following conversation concisely, preserving "
            "all key facts, decisions, and context needed for the agent "
            "to continue.\n\n"
            f"{rendered}"
        )
        raw = await llm.chat([{"role": "user", "content": summary_prompt}])
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
