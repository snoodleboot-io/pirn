"""``PromptChainPipeline`` — run a fixed sequence of LLM calls, chaining outputs.

A :class:`SubTapestry` that walks an ordered list of instruction ``steps``: the
first link runs against the initial ``task``; each subsequent link runs against
the previous link's output. This is the simplest agentic composition — a
deterministic pipeline of prompts with no branching — and is bounded by the number
of steps. Each link runs as a real, individually-traceable knot via
:class:`~pirn.nodes.aggregator.Aggregator`
(a :class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry`), instead of a
hand-rolled Python ``for`` loop (ADR agents-speaks-core WS5b). Returns a typed
:class:`PromptChainResult`.

References:
    - Anthropic (2024) "Building effective agents" — prompt chaining
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.prompt_chaining.prompt_chain_result import (
    PromptChainResult,
)
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall


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

        links: dict[str, Knot] = {}
        current: Knot | str = task
        for index, step in enumerate(step_tuple):
            current = LLMChatCall(
                prompt=current,
                llm=llm,
                system=step,
                _config=KnotConfig(id=f"link_{index}"),
            )
            links[f"link_{index}"] = current
        return Aggregator(
            combine=functools.partial(PromptChainPipeline._collect, tuple(links)),
            _config=KnotConfig(id="prompt_chain_result"),
            **links,
        )

    @staticmethod
    def _collect(order: tuple[str, ...], **outputs: str) -> PromptChainResult:
        """Aggregator combine (bound to ``order`` with ``functools.partial``).

        ``order`` fixes the link order, so the chain's outputs are reassembled
        in the order the steps were declared rather than the order the parent
        kwargs happen to arrive in.

        Args:
            order: The link keys in declaration order.
            outputs: Each link's text, keyed by its link id.

        Returns:
            The :class:`PromptChainResult` for the whole chain.
        """
        collected = tuple(outputs[key] for key in order)
        return PromptChainResult(outputs=collected, final=collected[-1])
