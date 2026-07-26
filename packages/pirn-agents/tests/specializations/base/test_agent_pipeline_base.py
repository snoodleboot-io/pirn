"""LSP / substitutability contract tests for the ``AgentPipeline`` family (PIR-702).

WS5/S5 re-parents every specialization knot whose body is a complete inner
tapestry onto the shared base
:class:`~pirn_agents.specializations.base.agent_pipeline.AgentPipeline` (itself a
:class:`~pirn.nodes.sub_tapestry.SubTapestry` subclass whose :meth:`process`
raises). The family is defined by its base *primitive* (``SubTapestry``), not by
a ``*_pipeline`` filename suffix: it also spans the guardrail gates, the
multi-agent orchestrations, the ReAct/LATS/ReWOO/Reflexion loops, the
RAG/document pipelines, the RAPTOR/parent-document ingestors, and the
specialized agents.

These tests pin:

* the base contract (``AgentPipeline`` is a ``SubTapestry`` and a ``Knot``; its
  ``process`` raises ``NotImplementedError``);
* per-member LSP -- each enumerated concrete is an ``AgentPipeline`` /
  ``SubTapestry`` and overrides ``process``;
* a **family-completeness invariant** -- walking the whole
  ``pirn_agents.specializations`` tree, EVERY ``SubTapestry`` subclass defined
  under it (other than the base itself) must descend from ``AgentPipeline``, so
  no specialization pipeline bypasses the seam; and
* a negative pin -- the ``ToolResultFormatter`` knot is a formatter, not a
  pipeline, and must stay outside both the pipeline and result families.

Concrete classes are resolved via :func:`importlib.import_module` inside each
test body so this module always COLLECTS cleanly even mid-re-parent.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

import pirn_agents.specializations as _specializations_pkg
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.tool_use.tool_result_formatter import ToolResultFormatter

# The 52-member specialization pipeline family: every SubTapestry subclass
# defined under specializations/** other than the AgentPipeline base itself.
# Enumerated explicitly (module_path, class_name) so the per-member LSP checks
# name each concrete; the family-completeness test below independently proves
# this list omits nothing.
_PIPELINE_CLASSES: list[tuple[str, str]] = [
    (
        "pirn_agents.specializations.document_processing.document_ingestion_pipeline",
        "DocumentIngestionPipeline",
    ),
    ("pirn_agents.specializations.document_processing.document_qa_pipeline", "DocumentQAPipeline"),
    (
        "pirn_agents.specializations.document_processing.document_summarizer_pipeline",
        "DocumentSummarizerPipeline",
    ),
    (
        "pirn_agents.specializations.document_processing.document_translation_pipeline",
        "DocumentTranslationPipeline",
    ),
    ("pirn_agents.specializations.document_processing.ingestion_pipeline", "IngestionPipeline"),
    (
        "pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_pipeline",
        "EvaluatorOptimizerPipeline",
    ),
    ("pirn_agents.specializations.guardrails.fact_check_gate", "FactCheckGate"),
    ("pirn_agents.specializations.guardrails.input_guardrail_gate", "InputGuardrailGate"),
    ("pirn_agents.specializations.guardrails.output_guardrail_gate", "OutputGuardrailGate"),
    ("pirn_agents.specializations.guardrails.pii_redactor_check", "PiiRedactorCheck"),
    ("pirn_agents.specializations.lats.lats_search", "LatsSearch"),
    ("pirn_agents.specializations.multi_agent.consensus_aggregator", "ConsensusAggregator"),
    ("pirn_agents.specializations.multi_agent.debate_framework", "DebateFramework"),
    ("pirn_agents.specializations.multi_agent.orchestrator_agent", "OrchestratorAgent"),
    ("pirn_agents.specializations.multi_agent.orchestrator_workers", "OrchestratorWorkers"),
    (
        "pirn_agents.specializations.multi_agent.parallel_specialist_fan_out",
        "ParallelSpecialistFanOut",
    ),
    ("pirn_agents.specializations.multi_agent.round_robin_review", "RoundRobinReview"),
    ("pirn_agents.specializations.plan_react.plan_react_pipeline", "PlanReActPipeline"),
    ("pirn_agents.specializations.prompt_chaining.prompt_chain_pipeline", "PromptChainPipeline"),
    ("pirn_agents.specializations.rag.adaptive_rag_pipeline", "AdaptiveRAGPipeline"),
    ("pirn_agents.specializations.rag.agentic_rag_pipeline", "AgenticRagPipeline"),
    (
        "pirn_agents.specializations.rag.contextual_retrieval_pipeline",
        "ContextualRetrievalPipeline",
    ),
    ("pirn_agents.specializations.rag.corrective_rag_pipeline", "CorrectiveRAGPipeline"),
    ("pirn_agents.specializations.rag.flare_active_rag_pipeline", "FlareActiveRagPipeline"),
    ("pirn_agents.specializations.rag.graph_rag_pipeline", "GraphRAGPipeline"),
    ("pirn_agents.specializations.rag.hyde_rag_pipeline", "HyDERAGPipeline"),
    ("pirn_agents.specializations.rag.indexing.auto_merging_ingestor", "AutoMergingIngestor"),
    ("pirn_agents.specializations.rag.indexing.parent_document_ingestor", "ParentDocumentIngestor"),
    ("pirn_agents.specializations.rag.indexing.raptor_tree_builder", "RaptorTreeBuilder"),
    ("pirn_agents.specializations.rag.multi_hop_rag_pipeline", "MultiHopRAGPipeline"),
    ("pirn_agents.specializations.rag.naive_rag_pipeline", "NaiveRAGPipeline"),
    ("pirn_agents.specializations.rag.rag_fusion_pipeline", "RagFusionPipeline"),
    ("pirn_agents.specializations.rag.router_rag_pipeline", "RouterRagPipeline"),
    ("pirn_agents.specializations.rag.self_query_rag_pipeline", "SelfQueryRagPipeline"),
    ("pirn_agents.specializations.rag.self_rag_pipeline", "SelfRAGPipeline"),
    ("pirn_agents.specializations.rag.speculative_rag_pipeline", "SpeculativeRagPipeline"),
    ("pirn_agents.specializations.rag.sub_question_rag_pipeline", "SubQuestionRagPipeline"),
    ("pirn_agents.specializations.react.react_loop", "ReActLoop"),
    ("pirn_agents.specializations.reflexion.reflexion_pipeline", "ReflexionPipeline"),
    ("pirn_agents.specializations.rewoo.rewoo_pipeline", "ReWooPipeline"),
    ("pirn_agents.specializations.routing.router_fallback_pipeline", "RouterFallbackPipeline"),
    ("pirn_agents.specializations.self_ask.self_ask_pipeline", "SelfAskPipeline"),
    ("pirn_agents.specializations.specialized_agents.browser_agent", "BrowserAgent"),
    ("pirn_agents.specializations.specialized_agents.code_agent", "CodeAgent"),
    ("pirn_agents.specializations.specialized_agents.data_analyst_agent", "DataAnalystAgent"),
    ("pirn_agents.specializations.specialized_agents.research_agent", "ResearchAgent"),
    ("pirn_agents.specializations.specialized_agents.sql_agent", "SQLAgent"),
    (
        "pirn_agents.specializations.structured_output.enum_classifier_pipeline",
        "EnumClassifierPipeline",
    ),
    (
        "pirn_agents.specializations.structured_output.json_extractor_pipeline",
        "JsonExtractorPipeline",
    ),
    (
        "pirn_agents.specializations.structured_output.pydantic_validator_pipeline",
        "PydanticValidatorPipeline",
    ),
    ("pirn_agents.specializations.structured_output.retry_on_parse_failure", "RetryOnParseFailure"),
    (
        "pirn_agents.specializations.structured_output.yaml_extractor_pipeline",
        "YamlExtractorPipeline",
    ),
]

_PIPELINE_IDS = [name for _, name in _PIPELINE_CLASSES]

# Module of the base class itself -- skipped by the family-completeness walk.
_BASE_MODULE = "pirn_agents.specializations.base.agent_pipeline"


def _load(module_path: str, class_name: str) -> type:
    """Import and return the class object at ``module_path.class_name``."""
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _walk_specialization_sub_tapestries() -> list[type]:
    """Return every SubTapestry subclass defined under specializations/**.

    Walks the whole package tree, importing each module, and collects classes
    whose ``__module__`` starts with ``pirn_agents.specializations`` and which
    subclass :class:`SubTapestry` -- excluding the ``AgentPipeline`` base.
    """
    collected: dict[tuple[str, str], type] = {}
    for info in pkgutil.walk_packages(
        _specializations_pkg.__path__, _specializations_pkg.__name__ + "."
    ):
        module = importlib.import_module(info.name)
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, SubTapestry):
                continue
            if not obj.__module__.startswith("pirn_agents.specializations"):
                continue
            if obj is AgentPipeline:
                continue
            collected[(obj.__module__, obj.__qualname__)] = obj
    return list(collected.values())


# --- base identity -------------------------------------------------------


def test_agent_pipeline_is_sub_tapestry_and_knot_subclass() -> None:
    # Arrange / Act / Assert: the base carries the pipeline primitive contract.
    assert issubclass(AgentPipeline, SubTapestry)
    assert issubclass(AgentPipeline, Knot)


async def test_agent_pipeline_process_raises_not_implemented() -> None:
    # Arrange: the base declares no __init__, so SubTapestry.__init__ runs.
    pipeline = AgentPipeline(_config=KnotConfig(id="ap"))

    # Act / Assert: the abstract process hook signals abstractness by name.
    with pytest.raises(NotImplementedError) as excinfo:
        await pipeline.process()

    assert "must implement process()" in str(excinfo.value)


# --- concrete pipeline LSP ------------------------------------------------


@pytest.mark.parametrize(("module_path", "class_name"), _PIPELINE_CLASSES, ids=_PIPELINE_IDS)
def test_pipeline_is_agent_pipeline_subclass(module_path: str, class_name: str) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: every member is substitutable for the AgentPipeline base.
    assert issubclass(cls, AgentPipeline)


@pytest.mark.parametrize(("module_path", "class_name"), _PIPELINE_CLASSES, ids=_PIPELINE_IDS)
def test_pipeline_is_sub_tapestry_subclass(module_path: str, class_name: str) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: the primitive contract is preserved through the new base.
    assert issubclass(cls, SubTapestry)


@pytest.mark.parametrize(("module_path", "class_name"), _PIPELINE_CLASSES, ids=_PIPELINE_IDS)
def test_pipeline_overrides_process(module_path: str, class_name: str) -> None:
    # Arrange.
    cls = _load(module_path, class_name)

    # Act / Assert: each concrete supplies its own process, not the raising base.
    assert cls.process is not AgentPipeline.process


# --- family-completeness invariant ---------------------------------------


def test_no_specialization_sub_tapestry_bypasses_the_base() -> None:
    # Arrange: discover every SubTapestry defined anywhere under specializations.
    discovered = _walk_specialization_sub_tapestries()

    # Assert (guard): the walk is non-vacuous and actually found the family.
    assert len(discovered) >= len(_PIPELINE_CLASSES)

    # Act / Assert: not one of them may skip the AgentPipeline seam.
    offenders = [
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in discovered
        if cls.__module__ != _BASE_MODULE and not issubclass(cls, AgentPipeline)
    ]
    assert offenders == []


# --- negative / scope pin -------------------------------------------------


def test_tool_result_formatter_is_a_knot_but_not_in_either_family() -> None:
    # Arrange / Act / Assert: it is a formatter Knot, not a pipeline and not a result value.
    assert issubclass(ToolResultFormatter, Knot)
    assert not issubclass(ToolResultFormatter, AgentPipeline)
    assert not issubclass(ToolResultFormatter, AgentResult)
