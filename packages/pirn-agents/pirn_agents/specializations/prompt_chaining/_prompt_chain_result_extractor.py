"""``_PromptChainResultExtractor`` — surface the chain's final :class:`PromptChainResult`.

Replaces the inline ``_PromptChainResultSource(Source)`` that closed over an
already-computed :class:`PromptChainResult` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass). Pure
extraction — no LLM/tool call here — mirroring
``_RetryResultExtractor``/``_CascadeResult``.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.prompt_chaining._prompt_chain_state import _PromptChainState
from pirn_agents.specializations.prompt_chaining.prompt_chain_result import PromptChainResult


class _PromptChainResultExtractor(Knot):
    """Wrap the chain loop's final state as a :class:`PromptChainResult`."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: _PromptChainState, **_: Any) -> PromptChainResult:
        """Return the chain's accumulated outputs and final value.

        Args:
            state: The chain loop's final accumulated state.

        Returns:
            The :class:`PromptChainResult` for the whole chain.
        """
        return PromptChainResult(outputs=state.outputs, final=state.outputs[-1])
