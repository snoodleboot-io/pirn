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
    3. Drive the attempts with a :class:`_RetryOnParseFailureLoop`
       (``LoopSubTapestry``): each attempt is one real, individually-traceable
       ``_LLMCallKnot`` invocation rather than a step inside a hand-rolled
       Python ``for`` loop (ADR agents-speaks-core WS5a). ``fold`` calls
       ``parser`` on each attempt's text and, on failure, builds the next
       attempt's retry prompt.
    4. Extract the parsed value with :class:`_RetryResultExtractor`, which
       raises ``ValueError`` if every attempt was exhausted without parsing.


References:
    - :class:`pirn_agents.specializations.structured_output._llm_call_knot._LLMCallKnot`
    - :class:`pirn.nodes.loop_sub_tapestry.LoopSubTapestry`
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.structured_output._retry_on_parse_failure_loop import (
    _RetryOnParseFailureLoop,
)
from pirn_agents.specializations.structured_output._retry_result_extractor import (
    _RetryResultExtractor,
)
from pirn_agents.specializations.structured_output._retry_state import _RetryState


class RetryOnParseFailure(AgentPipeline):
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
    ) -> Knot:
        """Wire the retry loop and return its parsed-value-extracting sink knot.

        Args:
            prompt: The initial prompt sent to the LLM.
            llm: The LLM provider used to generate responses.
            parser: Callable that parses the raw LLM text; raises on failure.
            max_retries: Maximum number of attempts before raising.

        Returns:
            The sink knot whose output is the first successfully parsed
            value from the parser callable.

        Raises:
            TypeError: If any argument is the wrong type.
            ValueError: If max_retries is not a positive int.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"RetryOnParseFailure: prompt must be a string, got {type(prompt).__name__}"
            )
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

        initial = Parameter(
            "retry_state",
            _RetryState,
            default=_RetryState(
                prompt=prompt,
                parsed_value=None,
                succeeded=False,
                last_error="no attempts were made",
                attempts=0,
            ),
        )
        loop = _RetryOnParseFailureLoop(
            original_prompt=prompt,
            llm=llm,
            parser=parser,
            max_retries=max_retries,
            state=initial,
            _config=KnotConfig(id="retry_loop"),
        )
        return _RetryResultExtractor(
            state=loop,
            _config=KnotConfig(id="result"),
        )
