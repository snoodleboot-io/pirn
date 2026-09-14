"""The registry must reach every shipped pattern — and keep reaching them (PIR-730).

``Agent.patterns()`` used to return ``("naive_rag", "rag", "react")`` while
``specializations/`` shipped 52 pipelines. The other 49 were reachable only by
importing and hand-wiring the class, so the facade advertised a breadth it did
not have, and nothing failed when a new pattern landed unregistered.

These tests close that both ways:

* **completeness** — the set of classes the registry builds is *exactly* the set
  of concrete pipelines under ``specializations/``, compared in both directions
  against an explicitly enumerated exclusion set, so neither an unregistered
  new pattern nor a quietly widened exclusion can pass;
* **resolvability** — every row actually imports, is a ``SubTapestry``, and
  declares a seed the constructor really has (``knot_class`` validates the row
  as it resolves it), so a table entry cannot rot against the class it names;
* **deferred resolution** — a row is data until something asks for the class,
  so the table stays declarative and the builder package does not import the
  specialization tree that points back at it.

No test here claims lazy targets shrink what a user loads, because they do not:
``pirn_agents/__init__.py`` calls ``Registry.fill_registry()``, which imports
every knot module in the package, so ``import pirn_agents`` already loads all
271 specialization modules (and, through them, ``numpy``) before this table is
consulted.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest
from pirn.nodes.sub_tapestry import SubTapestry
from sweet_tea.registry import Registry

import pirn_agents.specializations as _specializations_pkg
from pirn_agents.builder.agent_pattern_registry import AgentPatternRegistry
from pirn_agents.builder.pattern_descriptor import PatternDescriptor
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline

#: Family members that are deliberately not patterns a caller can name.
#: Compared by exact equality below, so this cannot be widened in silence.
_EXPECTED_EXCLUSIONS = frozenset(
    {
        # Abstract bases: a shared seam, not a pattern.
        "pirn_agents.specializations.base.agent_pipeline.AgentPipeline",
        "pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline",
        # Internal stage: the loop body EvaluatorOptimizerPipeline drives internally.
        "pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_loop"
        ".EvaluatorOptimizerLoop",
        # Iteration step: the per-turn body ReActLoop (registered as "react")
        # drives internally, one per unrolled turn. Not private by name (it
        # predates this exclusion set and is directly unit-tested on its own),
        # but not a standalone pattern either: its ``already_terminated``
        # constructor parameter is state only a driving loop can supply.
        "pirn_agents.specializations.react.react_step_executor.ReActStepExecutor",
        # Internal stage: the loop body IterativeRetriever drives internally (PIR-856).
        "pirn_agents.specializations.rag.iterative_retrieval_loop.IterativeRetrievalLoop",
        # Internal stage: the loop body RoundRobinReview drives internally
        # (ADR agents-speaks-core WS5a).
        "pirn_agents.specializations.multi_agent.round_robin_loop.RoundRobinLoop",
        # Internal stage: the loop body AgenticRagPipeline drives internally (PIR-856).
        "pirn_agents.specializations.rag.agentic_rag_loop.AgenticRagLoop",
        # Internal stage: the loop body RetryOnParseFailure drives internally
        # (ADR agents-speaks-core WS5a).
        "pirn_agents.specializations.structured_output.retry_on_parse_failure_loop"
        ".RetryOnParseFailureLoop",
        # Internal stage: the loop body SelfAskPipeline drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.self_ask.self_ask_loop.SelfAskLoop",
        # Internal stage: the loop body PromptChainPipeline drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.prompt_chaining.prompt_chain_loop.PromptChainLoop",
        # Internal stage: the loop body ConstitutionalFilter drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.reflection.constitutional_filter_loop"
        ".ConstitutionalFilterLoop",
        # Internal stage: the loop body JsonExtractorPipeline drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.structured_output.json_extractor_loop.JsonExtractorLoop",
        # Internal stage: the loop body YamlExtractorPipeline drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.structured_output.yaml_extractor_loop.YamlExtractorLoop",
        # Internal stage: the loop body PydanticValidatorPipeline drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.structured_output.pydantic_validator_loop"
        ".PydanticValidatorLoop",
        # Internal stage: the loop body ReflexionPipeline drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.reflexion.reflexion_loop.ReflexionLoop",
        # Internal stage: the loop body FlareActiveRagPipeline drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.rag.flare_loop.FlareLoop",
        # Internal stage: the complex-route arm AdaptiveRAGPipeline drives internally,
        # gated as a whole knot behind its Branch arm (ADR agents-speaks-core
        # WS5b) -- not a loop body, but the same "internal component another
        # pipeline wires, never named on its own" shape as CandidateAttempt.
        "pirn_agents.specializations.rag.complex_rag_arm.ComplexRagArm",
        # Internal stage: the loop body ModelCascadeRouter drives internally
        # (ADR agents-speaks-core WS5b).
        "pirn_agents.specializations.routing.cascade_loop.CascadeLoop",
        # Internal stage: the loop body FallbackChain drives internally (ADR
        # agents-speaks-core WS5b).
        "pirn_agents.specializations.routing.fallback_loop.FallbackLoop",
        # Internal stage: the per-candidate step FallbackChain drives internally (PIR-856).
        "pirn_agents.specializations.routing.candidate_attempt.CandidateAttempt",
        # PIR-867: newly AgentPipeline (was a plain Knot before its bypass fix)
        # — private fan-out bodies another pipeline drives internally.
        "pirn_agents.specializations.document_processing.chunk_embedder_store.ChunkEmbedderStore",
        "pirn_agents.specializations.document_processing.chunk_translator.ChunkTranslator",
        "pirn_agents.specializations.document_processing.ingestion_runner.IngestionRunner",
        "pirn_agents.specializations.plan_and_execute.plan_step_loop.PlanStepLoop",
        "pirn_agents.specializations.routing.attempt_tier.AttemptTier",
        # PIR-867: public but composed-internally, the same shape as
        # ReActStepExecutor's exclusion above — reachable only through the
        # pipeline that wires it (FactCheck registers as "fact_check").
        "pirn_agents.specializations.guardrails.fact_claim_verifier.FactClaimVerifier",
    }
)


def _qualified(cls: type) -> str:
    """Return ``module.QualName`` for a class."""
    return f"{cls.__module__}.{cls.__qualname__}"


def _discover_pipelines() -> dict[str, type]:
    """Return every :class:`AgentPipeline` subclass defined under specializations."""
    collected: dict[str, type] = {}
    for info in pkgutil.walk_packages(
        _specializations_pkg.__path__, _specializations_pkg.__name__ + "."
    ):
        module = importlib.import_module(info.name)
        for candidate in vars(module).values():
            if not isinstance(candidate, type):
                continue
            if not issubclass(candidate, AgentPipeline):
                continue
            if not candidate.__module__.startswith("pirn_agents.specializations"):
                continue
            collected[_qualified(candidate)] = candidate
    return collected


def _registered_classes() -> dict[str, type]:
    """Return every class the registry can build, keyed by qualified name."""
    return {
        _qualified(AgentPatternRegistry.pattern_class(name)): AgentPatternRegistry.pattern_class(
            name
        )
        for name in AgentPatternRegistry.pattern_names()
    }


# --- completeness ---------------------------------------------------------


def test_every_shipped_pipeline_is_reachable_by_name() -> None:
    # Arrange.
    discovered = _discover_pipelines()
    registered = _registered_classes()

    # Assert (guard): the walk is non-vacuous.
    assert len(discovered) > 40

    # Act: what ships but cannot be named.
    unreachable = sorted(set(discovered) - set(registered) - _EXPECTED_EXCLUSIONS)

    # Assert: register it in AgentPatternRegistry, or justify it in the
    # exclusion set above — silence is not an option.
    assert unreachable == []


def test_the_registry_names_nothing_that_is_not_a_shipped_pipeline() -> None:
    # Arrange / Act.
    discovered = _discover_pipelines()
    stale = sorted(set(_registered_classes()) - set(discovered))

    # Assert: the other direction — no row pointing at a class that moved away.
    assert stale == []


def test_every_registry_visible_agent_pipeline_has_seed_metadata() -> None:
    """PIR-870: cross-check against the *sweet_tea* Registry itself, not pkgutil.

    ``_discover_pipelines`` above walks the filesystem; this walks the very
    registry ``PatternDescriptor.knot_class()`` resolves classes through
    (``Registry.typed_entries(AgentPipeline)``, scoped to the ``pirn``
    library `fill_registry` filled). Every class it reports an ``AgentPipeline``
    subclass either has seed metadata here (a row's ``class_name`` names it) or
    is one of the already-justified exclusions -- so a class that is
    registry-visible but was never fed into this table (e.g. a future change to
    how the registry is filled) cannot pass silently.
    """
    # Arrange. ``pattern_names()`` is one row per pattern name.
    named_classes = {
        AgentPatternRegistry.descriptor(name).class_name
        for name in AgentPatternRegistry.pattern_names()
    }
    exclusion_class_names = {excluded.rsplit(".", 1)[1] for excluded in _EXPECTED_EXCLUSIONS}

    # Act.
    missing = []
    for entry in Registry.typed_entries(AgentPipeline):
        if entry.library != "pirn":
            continue
        cls = entry.class_def
        if cls.__name__ in named_classes or cls.__name__ in exclusion_class_names:
            continue
        missing.append(_qualified(cls))

    # Assert: every registry-visible AgentPipeline is named or justified.
    assert sorted(set(missing)) == []


def test_the_exclusion_set_is_exactly_what_is_excluded() -> None:
    """Both directions: an exclusion must be real, and reality must be excluded."""
    # Arrange.
    discovered = _discover_pipelines()
    registered = _registered_classes()

    # Act.
    actually_excluded = set(discovered) - set(registered)

    # Assert: not a superset, not a subset — equal.
    assert actually_excluded == set(_EXPECTED_EXCLUSIONS)


#: Iteration-step exclusions: public classes still excluded because a
#: constructor parameter is state only a driving loop can supply (so a caller
#: could construct one but never usefully drive it standalone). Named
#: explicitly, like the private list below, so this category cannot be
#: widened in silence either.
_ITERATION_STEPS = frozenset(
    {
        "pirn_agents.specializations.react.react_step_executor.ReActStepExecutor",
    }
)

#: Public classes excluded not because a constructor parameter needs a driving
#: loop (that is ``_ITERATION_STEPS``), but because they are reachable only
#: through the pipeline that composes them: a caller can construct and run
#: either directly (nothing about the constructor forces otherwise), but the
#: registry names the composed pipeline instead — ``FactCheck`` ("fact_check")
#: for ``FactClaimVerifier``, and no composed plan-and-execute pipeline is
#: registered at all for ``PlanExecutor`` (PIR-867: both became ``AgentPipeline``
#: only when their engine-bypasses were fixed, so neither was ever "discovered"
#: — and therefore never needed this exclusion — before).
_COMPOSED_STAGES = frozenset(
    {
        "pirn_agents.specializations.guardrails.fact_claim_verifier.FactClaimVerifier",
        "pirn_agents.specializations.plan_and_execute.plan_executor.PlanExecutor",
    }
)


def _drivers_of(qualified: str, discovered: dict[str, type]) -> list[str]:
    """Return the other ``specializations`` modules that bind ``qualified``'s class.

    An internal stage is wired by the pipeline that drives it, so some module
    other than its own imports it; a class nothing else imports is a pattern a
    caller would have to name, not an internal stage.
    """
    cls = discovered[qualified]
    drivers: list[str] = []
    for info in pkgutil.walk_packages(
        _specializations_pkg.__path__, _specializations_pkg.__name__ + "."
    ):
        if info.name == cls.__module__:
            continue
        module = importlib.import_module(info.name)
        if any(value is cls for value in vars(module).values()):
            drivers.append(info.name)
    return drivers


def test_the_excluded_bases_are_bases_and_the_internal_stages_are_driven_internally() -> None:
    """The exclusions are justified by what the classes are, not by fiat."""
    # Arrange.
    discovered = _discover_pipelines()
    bases = {_qualified(AgentPipeline), _qualified(AgentLoopPipeline)}
    categorised = bases | _ITERATION_STEPS | _COMPOSED_STAGES

    # Act.
    internal = sorted(set(_EXPECTED_EXCLUSIONS) - categorised)
    undriven = [name for name in internal if not _drivers_of(name, discovered)]

    # Assert.
    for base in (AgentPipeline, AgentLoopPipeline):
        assert _qualified(base) in _EXPECTED_EXCLUSIONS
        assert base.__module__.startswith("pirn_agents.specializations.base")
    # Every internal stage is wired by another module (the pipeline driving it).
    assert undriven == []
    assert internal == sorted(
        [
            "pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_loop"
            ".EvaluatorOptimizerLoop",
            "pirn_agents.specializations.rag.iterative_retrieval_loop.IterativeRetrievalLoop",
            "pirn_agents.specializations.rag.agentic_rag_loop.AgenticRagLoop",
            "pirn_agents.specializations.routing.candidate_attempt.CandidateAttempt",
            "pirn_agents.specializations.multi_agent.round_robin_loop.RoundRobinLoop",
            "pirn_agents.specializations.structured_output.retry_on_parse_failure_loop"
            ".RetryOnParseFailureLoop",
            "pirn_agents.specializations.self_ask.self_ask_loop.SelfAskLoop",
            "pirn_agents.specializations.prompt_chaining.prompt_chain_loop.PromptChainLoop",
            "pirn_agents.specializations.reflection.constitutional_filter_loop"
            ".ConstitutionalFilterLoop",
            "pirn_agents.specializations.structured_output.json_extractor_loop.JsonExtractorLoop",
            "pirn_agents.specializations.structured_output.yaml_extractor_loop.YamlExtractorLoop",
            "pirn_agents.specializations.structured_output.pydantic_validator_loop"
            ".PydanticValidatorLoop",
            "pirn_agents.specializations.reflexion.reflexion_loop.ReflexionLoop",
            "pirn_agents.specializations.rag.flare_loop.FlareLoop",
            "pirn_agents.specializations.rag.complex_rag_arm.ComplexRagArm",
            "pirn_agents.specializations.routing.cascade_loop.CascadeLoop",
            "pirn_agents.specializations.routing.fallback_loop.FallbackLoop",
            "pirn_agents.specializations.document_processing.chunk_embedder_store"
            ".ChunkEmbedderStore",
            "pirn_agents.specializations.document_processing.chunk_translator.ChunkTranslator",
            "pirn_agents.specializations.document_processing.ingestion_runner.IngestionRunner",
            "pirn_agents.specializations.plan_and_execute.plan_step_loop.PlanStepLoop",
            "pirn_agents.specializations.routing.attempt_tier.AttemptTier",
        ]
    )
    # The named categories never overlap, so every exclusion has exactly one
    # justification: base, internal stage, iteration step or composed stage.
    named = [bases, _ITERATION_STEPS, _COMPOSED_STAGES]
    assert sum(len(category) for category in named) == len(categorised)


# --- resolvability --------------------------------------------------------


def test_every_row_resolves_to_a_sub_tapestry_with_the_seed_it_declares() -> None:
    # Arrange / Act: knot_class() validates the row while resolving it.
    for name in AgentPatternRegistry.pattern_names():
        descriptor = AgentPatternRegistry.descriptor(name)
        knot_class = descriptor.knot_class()

        # Assert.
        assert issubclass(knot_class, SubTapestry)
        assert descriptor.accepts(descriptor.seed)


def test_no_pattern_requires_its_own_seed_as_a_component() -> None:
    # Arrange / Act / Assert: the seed is bound from .input(...), never twice.
    for name in AgentPatternRegistry.pattern_names():
        descriptor = AgentPatternRegistry.descriptor(name)
        assert descriptor.seed not in descriptor.required_components()
        assert descriptor.seed not in descriptor.optional_parameters()


def test_every_pattern_has_exactly_one_name() -> None:
    """A pattern class is reachable under one name only (PIR-873: no second spelling)."""
    # Arrange.
    names = AgentPatternRegistry.pattern_names()

    # Act.
    classes = [AgentPatternRegistry.descriptor(name).class_name for name in names]

    # Assert: one row per name, and no class reachable under two names.
    assert len(set(names)) == len(names)
    assert sorted(name for name in set(classes) if classes.count(name) > 1) == []


# --- laziness -------------------------------------------------------------


def test_listing_and_resolving_names_never_touches_the_classes() -> None:
    """A row is data until asked for the class — that is what keeps it a table."""
    # Arrange: a row naming a class that is not registered anywhere.
    bogus = PatternDescriptor("bogus", "NoSuchClassAnywherePir870", "query")

    # Act / Assert: everything name-shaped works, with no registry lookup.
    assert bogus.name == "bogus"
    assert bogus.class_name == "NoSuchClassAnywherePir870"

    # Assert: only asking for the class fails, and it says which row.
    with pytest.raises(ImportError, match="NoSuchClassAnywherePir870"):
        bogus.knot_class()


def test_a_row_pointing_at_a_non_pipeline_is_rejected_on_resolution() -> None:
    # Arrange: a real class that is not a SubTapestry.
    bad = PatternDescriptor("bad", "Agent", "query")

    # Act / Assert.
    with pytest.raises(TypeError, match="must be a SubTapestry subclass"):
        bad.knot_class()


def test_a_row_declaring_a_seed_the_class_lacks_is_rejected() -> None:
    # Arrange: right class, wrong seed parameter.
    wrong = PatternDescriptor("wrong", "NaiveRAGPipeline", "prompt")

    # Act / Assert: the row is checked against the constructor it names.
    with pytest.raises(ValueError, match="is not a constructor parameter"):
        wrong.knot_class()


# --- documentation ---------------------------------------------------------

#: BUILDER.md and PATTERNS.md, read together — a pattern's class name only
#: needs to be mentioned in one of the two, not both.
_DOC_PATHS = (
    Path(__file__).resolve().parents[2] / "pirn_agents" / "builder" / "BUILDER.md",
    Path(__file__).resolve().parents[2] / "pirn_agents" / "PATTERNS.md",
)


def test_builder_and_patterns_docs_list_every_registered_pattern() -> None:
    """PIR-870: the class name of every registered pattern is documented somewhere.

    Generates the expected list from ``AgentPatternRegistry`` itself (not a
    second hand-typed copy) and checks each class name appears in the
    concatenated text of BUILDER.md and PATTERNS.md, so a pattern added to the
    registry without a matching doc update is caught here rather than left for
    a reader to notice.
    """
    # Arrange.
    combined_text = "\n".join(path.read_text() for path in _DOC_PATHS)
    class_names = {
        AgentPatternRegistry.descriptor(name).class_name
        for name in AgentPatternRegistry.pattern_names()
    }

    # Assert (guard): the two named in PIR-856/870 specifically.
    assert "ConsensusPipeline" in class_names
    assert "ConstitutionalFilter" in class_names

    # Act / Assert.
    undocumented = sorted(name for name in class_names if name not in combined_text)
    assert undocumented == []
