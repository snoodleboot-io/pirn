"""``RetryOnParseFailure`` — retry LLM structured-output requests on parse error.

A :class:`SubTapestry` that attempts to produce a valid structured
response up to ``max_retries`` times. On each parse failure the error
message is included in the retry prompt sent back to the LLM so it can
self-correct. Returns the first successfully parsed response or raises
:class:`ValueError` when all attempts are exhausted.

The ``parser`` callable receives the raw LLM text and must either
return the parsed value or raise an exception.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.structured_output._llm_call_knot import _LLMCallKnot
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class RetryOnParseFailure(SubTapestry):
    """Retry LLM calls on parse failure, feeding the error back as context."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        parser: Callable[[str], Any],
        _config: KnotConfig,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "RetryOnParseFailure: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not callable(parser):
            raise TypeError(
                "RetryOnParseFailure: parser must be callable, "
                f"got {type(parser).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                "RetryOnParseFailure: max_retries must be a positive int, "
                f"got {max_retries!r}"
            )
        self._llm = llm
        self._parser = parser
        self._max_retries = max_retries
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(
        self,
        prompt: str,
        **_: Any,
    ) -> Any:
        """Attempt to get a valid parsed response, retrying with error feedback on failure.

        Args:
            prompt: The initial prompt sent to the LLM.

        Returns:
            The first successfully parsed value from the parser callable.

        Raises:
            TypeError: If prompt is not a string.
            ValueError: If all retry attempts are exhausted without a successful parse.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "RetryOnParseFailure: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        current_prompt = prompt
        last_error: str = "no attempts were made"
        for attempt_index in range(self._max_retries):
            with Tapestry() as inner:
                _LLMCallKnot(
                    prompt=current_prompt,
                    llm=self._llm,
                    _config=KnotConfig(id=f"call_{attempt_index}"),
                )
            inner_result = await self._run_inner(inner)
            text = inner_result.outputs.get(f"call_{attempt_index}")
            if not isinstance(text, str):
                text = str(text) if text is not None else ""
            try:
                return self._parser(text)
            except Exception as exc:
                last_error = str(exc)
                current_prompt = (
                    f"{prompt}\n\nPrevious attempt failed with: {last_error}\n"
                    "Please fix the issue and try again."
                )
        raise ValueError(
            f"RetryOnParseFailure: exhausted {self._max_retries} "
            f"attempt(s); last error: {last_error}"
        )
