"""``RaptorLevelLoop`` — build one RAPTOR summary level per iteration.

Each level clusters the level below it, so the levels depend on each other, and
how many there are depends on ``max_levels`` and on when the level narrows to a
single root. The shape is unknown until the run, which is what
``LoopSubTapestry`` is for (knot-design-rules Rule 11) — reached here through
``AgentLoopPipeline``, which every ``SubTapestry`` under ``specializations/``
belongs to.

It replaces a ``while len(current) > 1 and level < max_levels:`` that awaited
``embedder.embed`` once per level and started an unrelated nested run for each
level's summaries — so the embedding calls were invisible to the run and the
summary rows of level 2 had no connection to level 1's (PIR-874). Now every
level is an iteration of one run: the per-cluster
:class:`~pirn_agents.specializations.rag.indexing.raptor_summary.RaptorSummary`
knots fan out, and the level's
:class:`~pirn_agents.specializations.rag.indexing.embedded_texts.EmbeddedTexts`
knot sits downstream of them, carrying the data dependency the sequential code
expressed by statement order.

Internal API. See ``raptor_assembler.py``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_result import RunResult
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.rag.indexing.embedded_texts import EmbeddedTexts
from pirn_agents.specializations.rag.indexing.raptor_level_state import RaptorLevelState
from pirn_agents.specializations.rag.indexing.raptor_node import RaptorNode
from pirn_agents.specializations.rag.indexing.raptor_summary import RaptorSummary


class RaptorLevelLoop(AgentLoopPipeline[RaptorLevelState]):
    """Summarize and embed one level above ``current`` each iteration."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _summary_prefix: ClassVar[str] = "summary_"
    _summaries_id: ClassVar[str] = "summaries"
    _vectors_id: ClassVar[str] = "vectors"

    def step(self, state: RaptorLevelState) -> tuple[Tapestry, RaptorLevelState] | None:
        """Build the next level's summary fan-out and embedding, or end the climb.

        Reads only: :meth:`fold` owns every change to the accumulated state.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The level's tapestry paired with ``state``, or ``None`` once a single
            root remains or ``max_levels`` is reached.
        """
        if len(state.current) <= 1 or state.level >= state.max_levels:
            return None
        clusters = state.clusters()
        level = state.level + 1
        with Tapestry() as iteration:
            provider = Parameter(
                "llm", LLMProvider, default=state.llm, _config=KnotConfig(id="llm")
            )
            # The knot id is the id of the node the cluster produces, so a
            # summary's lineage row names the node it became (PIR-872).
            per_cluster: dict[str, Knot] = {
                f"{self._summary_prefix}{index}": RaptorSummary(
                    texts=texts,
                    llm=provider,
                    _config=KnotConfig(id=f"{state.prefix}:{level}:{index}"),
                )
                for index, texts in enumerate(clusters)
            }
            summaries = Aggregator(
                combine=RaptorLevelLoop._in_cluster_order,
                _config=KnotConfig(id=type(self)._summaries_id),
                **per_cluster,
            )
            EmbeddedTexts(
                embedder=state.embedder,
                texts=summaries,
                _config=KnotConfig(id=type(self)._vectors_id),
            )
        return iteration, state

    def fold(self, state: RaptorLevelState, result: RunResult) -> RaptorLevelState:
        """Turn the level's summaries and vectors into its nodes.

        Args:
            state: State as ``step`` returned it.
            result: The level's run result, carrying the summaries and their
                vectors in cluster order.

        Returns:
            A state whose ``current`` is the new level and whose ``nodes``
            includes it.
        """
        summaries: Any = result.outputs[type(self)._summaries_id]
        vectors: Any = result.outputs[type(self)._vectors_id]
        level = state.level + 1
        built = tuple(
            RaptorNode.create(
                id=f"{state.prefix}:{level}:{index}",
                level=level,
                text=summary,
                vector=vectors[index],
            )
            for index, summary in enumerate(summaries)
        )
        return state.with_fields(level=level, current=built, nodes=(*state.nodes, *built))

    def step_id(self, state: RaptorLevelState, idx: int) -> str:
        """Name each level for run history."""
        return f"level_{idx}"

    @staticmethod
    def _in_cluster_order(**summaries: str) -> tuple[str, ...]:
        """Order the per-cluster summaries by their ``summary_<index>`` key.

        A level's nodes are addressed by position (``<prefix>:<level>:<index>``),
        so the order must come from the index and not from whichever summary
        call finished first.
        """
        ordered = sorted(summaries.items(), key=lambda item: int(item[0].removeprefix("summary_")))
        return tuple(summary for _key, summary in ordered)
