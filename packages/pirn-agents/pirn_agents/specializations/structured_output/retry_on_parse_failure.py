"""``RetryOnParseFailure`` — retry LLM structured-output requests on parse error.

A :class:`SubTapestry` that attempts to produce a valid structured
response up to ``max_retries`` times. On each parse failure the error
message is included in the retry prompt sent back to the LLM so it can
self-correct. Returns the first successfully parsed response or raises
:class:`ValueError` when all attempts are exhausted.

The ``parser`` callable receives the raw LLM text and must either
return the parsed value or raise an exception.

Algorithm:
    1. Receive ``prompt`` (str), ``llm`` (LLMProvider), ``parser`` (Callable),
       and ``max_retries`` (int).
    2. Validate each argument type; raise ``TypeError`` or ``ValueError``
       on invalid inputs.
    3. For each attempt index in ``range(max_retries)``:
       a. Build an inner Tapestry containing an ``_LLMCallKnot``.
       b. Await ``_run_inner`` to obtain the raw text output.
       c. Pass the text to ``parser``; if successful return the result.
       d. On parse failure, append the error to the prompt and retry.
    4. If all attempts fail, raise ``ValueError`` with the last error.


References:
    - :class:`pirn_agents.specializations.structured_output._llm_call_knot._LLMCallKnot`
    - :class:`pirn.nodes.sub_tapestry.SubTapestry`
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.structured_output._llm_call_knot import _LLMCallKnot


class RetryOnParseFailure(SubTapestry):
    """Retry LLM calls on parse failure, feeding the error back as context."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        parser: Knot | Callable[[str], Any],
        _config: KnotConfig,
        max_retries: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt,
            llm=llm,
            parser=parser,
            max_retries=max_retries,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prompt: str,
        llm: LLMProvider,
        parser: Callable[[str], Any],
        max_retries: int = 3,
        **_: Any,
    ) -> Any:
        """Attempt to get a valid parsed response, retrying with error feedback on failure.

        Args:
            prompt: The initial prompt sent to the LLM.
            llm: The LLM provider used to generate responses.
            parser: Callable that parses the raw LLM text; raises on failure.
            max_retries: Maximum number of attempts before raising.

        Returns:
            The first successfully parsed value from the parser callable.

        Raises:
            TypeError: If any argument is the wrong type.
            ValueError: If max_retries is not a positive int, or all attempts are exhausted.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"RetryOnParseFailure: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not callable(parser):
            raise TypeError(
                f"RetryOnParseFailure: parser must be callable, got {type(parser).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                f"RetryOnParseFailure: max_retries must be a positive int, got {max_retries!r}"
            )
        if not isinstance(prompt, str):
            raise TypeError(
                f"RetryOnParseFailure: prompt must be a string, got {type(prompt).__name__}"
            )
        current_prompt = prompt
        last_error: str = "no attempts were made"
        parsed_value: Any = None
        succeeded = False
        for attempt_index in range(max_retries):
            with Tapestry() as attempt_tapestry:
                _LLMCallKnot(
                    prompt=current_prompt,
                    llm=llm,
                    _config=KnotConfig(id=f"call_{attempt_index}"),
                )
            inner_result = await self._run_inner(attempt_tapestry)
            text = inner_result.outputs.get(f"call_{attempt_index}")
            if not isinstance(text, str):
                text = str(text) if text is not None else ""
            try:
                parsed_value = parser(text)
                succeeded = True
                break
            except Exception as exc:
                last_error = str(exc)
                current_prompt = (
                    f"{prompt}\n\nPrevious attempt failed with: {last_error}\n"
                    "Please fix the issue and try again."
                )
        if not succeeded:
            raise ValueError(
                f"RetryOnParseFailure: exhausted {max_retries} attempt(s); last error: {last_error}"
            )
        _value = parsed_value

        class _ResultSource(Source):
            async def process(self, **_: Any) -> Any:
                return _value

        return _ResultSource(_config=KnotConfig(id="result"))
