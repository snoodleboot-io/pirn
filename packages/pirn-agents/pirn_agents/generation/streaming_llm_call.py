"""``StreamingLLMCall`` — return an async iterator of streamed chat chunks.

Algorithm:
    1. Receive the resolved ``AgentContext`` and ``LLMProvider``.
    2. Validate input types at process time.
    3. Convert context messages to wire-format role/content mappings.
    4. Call ``llm.stream_chat`` with the wire messages and optional model override.
    5. Return the async iterator of chunk mappings directly to the caller.


References:
    - :class:`pirn_agents.llm.llm_provider.LLMProvider`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.types.messaging.agent_context import AgentContext


class StreamingLLMCall(Knot):
    """Hands back an :class:`AsyncIterator` of streamed chat fragments.

    The iterator is constructed by invoking
    :meth:`LLMProvider.stream_chat`; the knot itself does not consume
    the stream so callers retain full control over fragment handling.
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
    ) -> Any:
        """Invoke the LLM streaming interface and return an async iterator of response chunks.

        Args:
            context: The agent context containing the messages to stream.
            llm: LLM provider used to perform the streaming chat completion.
            model: Optional model identifier override; uses the provider default if None.

        Returns:
            An async iterator of :class:`~pirn_agents.llm.stream_delta.StreamDelta`
            fragments from the LLM provider.

        Raises:
            TypeError: If context is not an AgentContext or llm is not an LLMProvider.
            ValueError: If model is an empty string.
        """
        # Return type elided to ``Any`` because pydantic's ``TypeAdapter``
        # cannot produce a schema for :class:`AsyncIterator`; downstream
        # callers narrow back to ``AsyncIterator[StreamDelta]`` by iterating
        # the result.
        #
        # The provider call is deliberately NOT awaited (PIR-833): every
        # provider implements ``stream_chat`` as an async generator, so the
        # call already yields the iterator this knot hands back. It used to be
        # awaited — which the interface's own ``async def`` declaration invited
        # — and that raises ``TypeError`` against any real provider; only test
        # doubles that returned an iterator from a coroutine made it work.
        if not isinstance(context, AgentContext):
            raise TypeError(
                f"StreamingLLMCall: context must be an AgentContext, got {type(context).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"StreamingLLMCall: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if model is not None and (not isinstance(model, str) or not model):
            raise ValueError(
                f"StreamingLLMCall: model must be a non-empty string or None, got {model!r}"
            )
        wire_messages = tuple(
            {"role": message.role, "content": message.content} for message in context.messages
        )
        return llm.stream_chat(messages=wire_messages, model=model)
