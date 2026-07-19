"""``LLMCall`` — non-streaming chat-completion against an :class:`LLMProvider`.

Algorithm:
    1. Receive the resolved ``AgentContext`` and ``LLMProvider``.
    2. Validate input types at process time.
    3. Convert context messages to wire-format role/content mappings.
    4. Call ``llm.chat`` with the wire messages and optional model override.
    5. Return the raw response mapping from the provider.


References:
    - :class:`pirn_agents.llm_provider.LLMProvider`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.types.agent_context import AgentContext


class LLMCall(Knot):
    """Calls :meth:`LLMProvider.chat` and returns the raw response mapping.

    The knot itself adds no prompt mutation — it is a thin, auditable
    bridge between the typed pipeline and the provider.
    """

    def __init__(
        self,
        *,
        context: Knot,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        model: Knot | str | None = None,
        **kwargs: Any,
    ) -> None:
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
            TypeError: If context is not an AgentContext or llm is not an LLMProvider.
            ValueError: If model is an empty string.
        """
        if not isinstance(context, AgentContext):
            raise TypeError(
                f"LLMCall: context must be an AgentContext, got {type(context).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"LLMCall: llm must be an LLMProvider, got {type(llm).__name__}")
        if model is not None and (not isinstance(model, str) or not model):
            raise ValueError(f"LLMCall: model must be a non-empty string or None, got {model!r}")
        wire_messages = tuple(
            {"role": message.role, "content": message.content} for message in context.messages
        )
        return await llm.chat(messages=wire_messages, model=model)
