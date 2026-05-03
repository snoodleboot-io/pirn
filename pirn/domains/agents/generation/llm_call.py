"""``LLMCall`` — non-streaming chat-completion against an :class:`LLMProvider`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_context import AgentContext


class LLMCall(Knot):
    """Calls :meth:`LLMProvider.chat` and returns the raw response mapping.

    The knot itself adds no prompt mutation — it is a thin, auditable
    bridge between the typed pipeline and the provider.
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
                "LLMCall: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if model is not None and (not isinstance(model, str) or not model):
            raise ValueError(
                "LLMCall: model must be a non-empty string or None, "
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
    ) -> Mapping[str, Any]:
        """Call the LLM with the context messages and return the raw response mapping.

        Args:
            context: The agent context containing the messages to send.
            llm: LLM provider used to perform the chat completion.
            model: Optional model identifier override; uses the provider default if None.

        Returns:
            The raw response mapping returned by the LLM provider.

        Raises:
            TypeError: If context is not an AgentContext instance.
        """
        if not isinstance(context, AgentContext):
            raise TypeError(
                "LLMCall: context must be an AgentContext, "
                f"got {type(context).__name__}"
            )
        wire_messages = tuple(
            {"role": message.role, "content": message.content}
            for message in context.messages
        )
        return await llm.chat(messages=wire_messages, model=model)
