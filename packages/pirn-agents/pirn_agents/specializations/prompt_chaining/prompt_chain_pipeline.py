"""``PromptChainPipeline`` — run a fixed sequence of LLM calls, chaining outputs.

A :class:`SubTapestry` that walks an ordered list of instruction ``steps``: the
first link runs against the initial ``task``; each subsequent link runs against
the previous link's output. This is the simplest agentic composition — a
deterministic pipeline of prompts with no branching — and is bounded by the number
of steps. Returns a typed :class:`PromptChainResult`.

References:
    - Anthropic (2024) "Building effective agents" — prompt chaining
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.prompt_chaining.prompt_chain_result import PromptChainResult


class PromptChainPipeline(SubTapestry):
    """Sequentially chain LLM calls, feeding each output into the next step."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        steps: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, llm=llm, steps=steps, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        steps: Sequence[str],
        **_: Any,
    ) -> Any:
        """Run the prompt chain and surface a :class:`PromptChainResult`.

        Args:
            task: The initial input fed to the first link.
            llm: Provider used for every link.
            steps: Ordered instruction strings, one per link.

        Returns:
            A terminal :class:`Source` whose output is the
            :class:`PromptChainResult`.

        Raises:
            TypeError: If ``task`` is not a string, ``llm`` is not an
                :class:`LLMProvider`, or a step is not a string.
            ValueError: If ``steps`` is empty.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"PromptChainPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(
                f"PromptChainPipeline: task must be a string, got {type(task).__name__}"
            )
        step_tuple = tuple(steps)
        if not step_tuple:
            raise ValueError("PromptChainPipeline: steps must be a non-empty sequence")
        for index, step in enumerate(step_tuple):
            if not isinstance(step, str):
                raise TypeError(
                    f"PromptChainPipeline: steps[{index}] must be a str, got {type(step).__name__}"
                )

        outputs: list[str] = []
        current = task
        for step in step_tuple:
            raw = await llm.chat(
                messages=[
                    {"role": "system", "content": step},
                    {"role": "user", "content": current},
                ]
            )
            current = LlmResponseText().extract(raw)
            outputs.append(current)

        result = PromptChainResult(outputs=tuple(outputs), final=outputs[-1])
        _result = result

        class _PromptChainResultSource(Source):
            async def process(self, **_: Any) -> PromptChainResult:
                return _result

        return _PromptChainResultSource(_config=KnotConfig(id="prompt_chain_result"))
