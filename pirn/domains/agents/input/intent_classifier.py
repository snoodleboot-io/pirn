"""``IntentClassifier`` — pick the closest declared intent for a context.

Algorithm:
    1. Receive the resolved ``AgentContext``, ``LLMProvider``, and ``intent_categories``.
    2. Validate input types at process time.
    3. Extract the last user message from the context.
    4. Build a classification prompt with the intent category labels.
    5. Call ``llm.chat`` with the prompt.
    6. Extract text from the raw response.
    7. Try exact lower-case match, then substring match against intent labels.
    8. Raise ``ValueError`` if no match found.


References:
    - :class:`pirn.domains.agents.llm_provider.LLMProvider`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_context import AgentContext


class IntentClassifier(Knot):
    """Asks an :class:`LLMProvider` to map a context to one of ``intent_categories``.

    The LLM is prompted with the candidate intent labels; its raw text
    response (extracted from the chat-completion mapping) is normalised
    to lower case and matched against the declared intents. Falls back
    to the first intent that appears as a substring of the response. If
    nothing matches, raises ``ValueError``.
    """

    def __init__(
        self,
        *,
        context: Knot,
        llm: Knot | LLMProvider,
        intent_categories: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            context=context,
            llm=llm,
            intent_categories=intent_categories,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        context: AgentContext,
        llm: LLMProvider,
        intent_categories: Sequence[str],
        **_: Any,
    ) -> str:
        """Ask the LLM to classify the context into one of the declared intent categories.

        Args:
            context: The agent context whose last user message is classified.
            llm: LLM provider used to perform the classification.
            intent_categories: The set of allowed intent label strings.

        Returns:
            The matched intent label string from the declared categories.

        Raises:
            TypeError: If inputs have wrong types.
            ValueError: If intent_categories is empty or the LLM response matches no intent.
        """
        if not isinstance(context, AgentContext):
            raise TypeError(
                "IntentClassifier: context must be an AgentContext, "
                f"got {type(context).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "IntentClassifier: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(intent_categories, Sequence) or isinstance(
            intent_categories, (str, bytes)
        ):
            raise TypeError(
                "IntentClassifier: intent_categories must be a sequence of strings"
            )
        if not intent_categories:
            raise ValueError(
                "IntentClassifier: intent_categories must be non-empty"
            )
        for index, intent in enumerate(intent_categories):
            if not isinstance(intent, str) or not intent:
                raise ValueError(
                    f"IntentClassifier: intent_categories[{index}] must be a "
                    f"non-empty string, got {intent!r}"
                )
        last = self._last_user_content(context)
        prompt = (
            "Classify the following message into exactly one of these "
            f"intents: {', '.join(intent_categories)}.\n\n"
            f"Message: {last}\n\n"
            "Respond with the chosen intent label only."
        )
        response = await llm.chat(
            messages=({"role": "user", "content": prompt},),
        )
        raw = self._extract_text(response)
        normalised = raw.strip().lower()
        for intent in intent_categories:
            if intent.lower() == normalised:
                return intent
        for intent in intent_categories:
            if intent.lower() in normalised:
                return intent
        raise ValueError(
            f"IntentClassifier: LLM response {raw!r} did not match any "
            f"declared intent {list(intent_categories)!r}"
        )

    def _last_user_content(self, context: AgentContext) -> str:
        for message in reversed(context.messages):
            if message.role == "user":
                return message.content
        if context.messages:
            return context.messages[-1].content
        raise ValueError(
            "IntentClassifier: context has no messages to classify"
        )

    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            content = response.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict) and isinstance(first.get("text"), str):
                    return first["text"]
        raise TypeError(
            "IntentClassifier: cannot extract text from LLM response of type "
            f"{type(response).__name__}"
        )
