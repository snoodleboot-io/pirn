"""``StreamingLLMCall`` — return an async iterator of streamed chat chunks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_context import AgentContext


class StreamingLLMCall(Knot):
    """Hands back an :class:`AsyncIterator` of streamed chat chunks.

    The iterator is constructed by invoking
    :meth:`LLMProvider.stream_chat`; the knot itself does not consume
    the stream so callers retain full control over chunk handling.
    """

    def __init__(
        self,
        *,
        context: Knot,
        llm: LLMProvider,
        _config: KnotConfig,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "StreamingLLMCall: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if model is not None and (not isinstance(model, str) or not model):
            raise ValueError(
                "StreamingLLMCall: model must be a non-empty string or None, "
                f"got {model!r}"
            )
        super().__init__(
            context=context,
            llm=llm,
            model=model,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        context: AgentContext,
        llm: LLMProvider,
        model: str | None,
        **_: Any,
    ) -> Any:
        """Invoke the LLM streaming interface and return an async iterator of response chunks.

        Args:
            context: The agent context containing the messages to stream.
            llm: LLM provider used to perform the streaming chat completion.
            model: Optional model identifier override; uses the provider default if None.

        Returns:
            An async iterator of response chunk mappings from the LLM provider.

        Raises:
            TypeError: If context is not an AgentContext instance.
        """
        # Return type elided to ``Any`` because pydantic's ``TypeAdapter``
        # cannot produce a schema for :class:`AsyncIterator`; downstream
        # callers narrow back to ``AsyncIterator[Mapping[str, Any]]``
        # by iterating the result.
        if not isinstance(context, AgentContext):
            raise TypeError(
                "StreamingLLMCall: context must be an AgentContext, "
                f"got {type(context).__name__}"
            )
        wire_messages = tuple(
            {"role": message.role, "content": message.content}
            for message in context.messages
        )
        return await llm.stream_chat(messages=wire_messages, model=model)
