# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``PromptChainPipeline`` — run a fixed sequence of LLM calls, chaining outputs.

A :class:`SubTapestry` that walks an ordered list of instruction ``steps``: the
first link runs against the initial ``task``; each subsequent link runs against
the previous link's output. This is the simplest agentic composition — a
deterministic pipeline of prompts with no branching — and is bounded by the number
of steps. Each link runs as a real, individually-traceable knot via
:class:`~pirn_agents.specializations.prompt_chaining._prompt_chain_loop.PromptChainLoop`
(a :class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry`), instead of a
hand-rolled Python ``for`` loop (ADR agents-speaks-core WS5b). Returns a typed
:class:`PromptChainResult`.

References:
    - Anthropic (2024) "Building effective agents" — prompt chaining
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.prompt_chaining._prompt_chain_loop import PromptChainLoop
from pirn_agents.specializations.prompt_chaining._prompt_chain_result_extractor import (
    PromptChainResultExtractor,
)
from pirn_agents.specializations.prompt_chaining._prompt_chain_state import PromptChainState


class PromptChainPipeline(AgentPipeline):
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
    ) -> Knot:
        """Run the prompt chain and surface a :class:`PromptChainResult`.

        Args:
            task: The initial input fed to the first link.
            llm: Provider used for every link.
            steps: Ordered instruction strings, one per link.

        Returns:
            The sink knot whose output is the :class:`PromptChainResult`.

        Raises:
            TypeError: If ``task`` is not a string, ``llm`` is not an
                :class:`LLMProvider`, or a step is not a string.
            ValueError: If ``steps`` is empty.
        """
        step_tuple = tuple(steps)
        if not step_tuple:
            raise ValueError("PromptChainPipeline: steps must be a non-empty sequence")
        for index, step in enumerate(step_tuple):
            if not isinstance(step, str):
                raise TypeError(
                    f"PromptChainPipeline: steps[{index}] must be a str, got {type(step).__name__}"
                )

        initial = Parameter(
            "prompt_chain_state",
            PromptChainState,
            default=PromptChainState(steps=step_tuple, index=0, current=task, outputs=()),
        )
        loop = PromptChainLoop(
            llm=llm,
            state=initial,
            _config=KnotConfig(id="prompt_chain_loop"),
        )
        return PromptChainResultExtractor(state=loop, _config=KnotConfig(id="prompt_chain_result"))
