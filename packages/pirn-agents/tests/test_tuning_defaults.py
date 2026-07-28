"""Characterization tests pinning the package's shared tuning defaults (PIR-707).

Every value asserted here is a knob that used to be re-declared as a bare literal
at several call sites. The tests read the *effective* default off each public
signature (via :func:`inspect.signature`) rather than the config object, so they
stay honest about what a caller actually gets — and they fail loudly if
centralising a knob silently shifts one site's default.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import pytest

from pirn_agents.agent.agent_invoker import AgentInvoker
from pirn_agents.agent.agent_tool_context import AgentToolContext
from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.memory.management.near_duplicate_grouper import NearDuplicateGrouper
from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from pirn_agents.specializations.document_processing.chunking.fixed_size_chunking_strategy import (
    FixedSizeChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.recursive_character_chunking_strategy import (
    RecursiveCharacterChunkingStrategy,
)
from pirn_agents.specializations.document_processing.document_ingestion_pipeline import (
    DocumentIngestionPipeline,
)
from pirn_agents.specializations.document_processing.document_qa_pipeline import (
    DocumentQAPipeline,
)
from pirn_agents.specializations.document_processing.ingestion_pipeline import (
    IngestionPipeline,
)
from pirn_agents.specializations.multi_agent.orchestrator_workers import OrchestratorWorkers
from pirn_agents.specializations.rag.graph_rag_pipeline import GraphRAGPipeline
from pirn_agents.specializations.rewoo.rewoo_pipeline import ReWooPipeline
from pirn_agents.tools.agent_as_tool_mixin import AgentAsToolMixin
from pirn_agents.tools.agent_tool import AgentTool
from pirn_agents.tools.as_tool import as_tool


def _default_of(target: Callable[..., Any], parameter: str) -> Any:
    """Return the effective default of ``parameter`` on ``target``'s signature."""
    return inspect.signature(target).parameters[parameter].default


class TestAgentNestingDepthDefaults:
    """``max_depth`` — the agent-as-tool recursion cap, one value across the chain."""

    @pytest.mark.parametrize(
        "target",
        [
            AgentInvoker.__init__,
            AgentTool.__init__,
            as_tool,
            AgentAsToolMixin.as_tool,
        ],
    )
    def test_max_depth_default_is_eight(self, target: Callable[..., Any]) -> None:
        assert _default_of(target, "max_depth") == 8

    def test_context_field_default_is_eight(self) -> None:
        assert AgentToolContext().max_depth == 8

    def test_root_context_seeded_by_invoker_uses_the_same_cap(self) -> None:
        invoker = AgentInvoker()

        assert invoker._max_depth == AgentToolContext().max_depth

    def test_chain_agrees_end_to_end(self) -> None:
        depths = {
            _default_of(AgentInvoker.__init__, "max_depth"),
            _default_of(AgentTool.__init__, "max_depth"),
            _default_of(as_tool, "max_depth"),
            _default_of(AgentAsToolMixin.as_tool, "max_depth"),
            AgentToolContext().max_depth,
        }

        assert depths == {8}


class TestConcurrencyDefaults:
    """``max_concurrency`` — the shared bounded-concurrency posture."""

    def test_config_default(self) -> None:
        assert ConcurrencyConfig().max_concurrency == 8

    @pytest.mark.parametrize(
        "target",
        [
            ParallelToolExecutor.__init__,
            OrchestratorWorkers.__init__,
            OrchestratorWorkers.process,
            ReWooPipeline.__init__,
            ReWooPipeline.process,
            IngestionPipeline.__init__,
            IngestionPipeline.process,
        ],
    )
    def test_call_sites_default_to_eight(self, target: Callable[..., Any]) -> None:
        assert _default_of(target, "max_concurrency") == 8

    def test_parallel_executor_process_requires_an_explicit_bound(self) -> None:
        default = _default_of(ParallelToolExecutor.process, "max_concurrency")

        assert default is inspect.Parameter.empty


class TestRetrievalBreadthDefaults:
    """``top_k`` for the graph-RAG sub-graph fetch."""

    def test_graph_rag_retrieval_top_k(self) -> None:
        assert GraphRAGPipeline._retrieval_top_k == 25


class TestChunkGeometryDefaults:
    """Default chunk size/overlap for document processing."""

    def test_document_qa_chunk_size(self) -> None:
        assert DocumentQAPipeline._default_chunk_size == 1000

    @pytest.mark.parametrize(
        "target",
        [
            DocumentIngestionPipeline.__init__,
            DocumentIngestionPipeline.process,
            FixedSizeChunkingStrategy.__init__,
            RecursiveCharacterChunkingStrategy.__init__,
        ],
    )
    def test_chunk_size_default(self, target: Callable[..., Any]) -> None:
        assert _default_of(target, "chunk_size") == 1000

    @pytest.mark.parametrize(
        "target",
        [
            DocumentIngestionPipeline.__init__,
            DocumentIngestionPipeline.process,
            FixedSizeChunkingStrategy.__init__,
            RecursiveCharacterChunkingStrategy.__init__,
        ],
    )
    def test_chunk_overlap_default(self, target: Callable[..., Any]) -> None:
        assert _default_of(target, "chunk_overlap") == 100


class TestNearDuplicateThresholdDefault:
    """The consolidation near-duplicate similarity floor."""

    def test_threshold(self) -> None:
        assert NearDuplicateGrouper().threshold == 0.6
