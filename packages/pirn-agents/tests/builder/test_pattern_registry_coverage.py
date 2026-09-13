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

import pytest
from pirn.nodes.sub_tapestry import SubTapestry

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
        # Private: the loop body EvaluatorOptimizerPipeline drives internally.
        "pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_loop"
        "._EvaluatorOptimizerLoop",
        # Iteration step: the per-turn body ReActLoop (registered as "react")
        # drives internally, one per unrolled turn. Not private by name (it
        # predates this exclusion set and is directly unit-tested on its own),
        # but not a standalone pattern either: its ``already_terminated``
        # constructor parameter is state only a driving loop can supply.
        "pirn_agents.specializations.react.react_step_executor.ReActStepExecutor",
        # Private: the loop body IterativeRetriever drives internally (PIR-856).
        "pirn_agents.specializations.rag._iterative_retrieval_loop._IterativeRetrievalLoop",
        # Private: the loop body RoundRobinReview drives internally
        # (ADR agents-speaks-core WS5a).
        "pirn_agents.specializations.multi_agent._round_robin_loop._RoundRobinLoop",
        # Private: the loop body AgenticRagPipeline drives internally (PIR-856).
        "pirn_agents.specializations.rag._agentic_rag_loop._AgenticRagLoop",
        # Private: the per-candidate step FallbackChain drives internally (PIR-856).
        "pirn_agents.specializations.routing._candidate_attempt._CandidateAttempt",
        # Deprecated *Gate aliases (PIR-856, Knot Design Rule 7): reachable only
        # under their replacement *Check name, which is what is registered.
        "pirn_agents.specializations.guardrails.fact_check_gate.FactCheckGate",
        "pirn_agents.specializations.guardrails.input_guardrail_gate.InputGuardrailGate",
        "pirn_agents.specializations.guardrails.output_guardrail_gate.OutputGuardrailGate",
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
        for name in AgentPatternRegistry.canonical_names()
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

#: Deprecated ``*Gate`` alias classes (PIR-856, Knot Design Rule 7): each is a
#: thin subclass kept importable for one cycle; the registry names the
#: replacement ``*Check`` class, so the alias itself is never reachable by name.
_DEPRECATED_ALIASES = frozenset(
    {
        "pirn_agents.specializations.guardrails.fact_check_gate.FactCheckGate",
        "pirn_agents.specializations.guardrails.input_guardrail_gate.InputGuardrailGate",
        "pirn_agents.specializations.guardrails.output_guardrail_gate.OutputGuardrailGate",
    }
)


def test_the_excluded_bases_are_bases_and_the_excluded_private_is_private() -> None:
    """The exclusions are justified by what the classes are, not by fiat."""
    # Arrange / Act / Assert.
    for base in (AgentPipeline, AgentLoopPipeline):
        assert _qualified(base) in _EXPECTED_EXCLUSIONS
        assert base.__module__.startswith("pirn_agents.specializations.base")
    private = sorted(
        name for name in _EXPECTED_EXCLUSIONS if name.rsplit(".", 1)[1].startswith("_")
    )
    assert private == sorted(
        [
            "pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_loop"
            "._EvaluatorOptimizerLoop",
            "pirn_agents.specializations.rag._iterative_retrieval_loop._IterativeRetrievalLoop",
            "pirn_agents.specializations.rag._agentic_rag_loop._AgenticRagLoop",
            "pirn_agents.specializations.routing._candidate_attempt._CandidateAttempt",
            "pirn_agents.specializations.multi_agent._round_robin_loop._RoundRobinLoop",
        ]
    )
    # Every exclusion falls into exactly one justified category: base,
    # private loop body, or named iteration step.
    bases = {_qualified(AgentPipeline), _qualified(AgentLoopPipeline)}
    # Every exclusion falls into exactly one justified category: base,
    # private loop body, named iteration step, or deprecated alias.
    assert _EXPECTED_EXCLUSIONS == bases | set(private) | _ITERATION_STEPS | _DEPRECATED_ALIASES
    for alias in _DEPRECATED_ALIASES:
        assert alias.rsplit(".", 1)[1].endswith("Gate")


# --- resolvability --------------------------------------------------------


def test_every_row_resolves_to_a_sub_tapestry_with_the_seed_it_declares() -> None:
    # Arrange / Act: knot_class() validates the row while resolving it.
    for name in AgentPatternRegistry.canonical_names():
        descriptor = AgentPatternRegistry.descriptor(name)
        knot_class = descriptor.knot_class()

        # Assert.
        assert issubclass(knot_class, SubTapestry)
        assert descriptor.accepts(descriptor.seed)


def test_no_pattern_requires_its_own_seed_as_a_component() -> None:
    # Arrange / Act / Assert: the seed is bound from .input(...), never twice.
    for name in AgentPatternRegistry.canonical_names():
        descriptor = AgentPatternRegistry.descriptor(name)
        assert descriptor.seed not in descriptor.required_components()
        assert descriptor.seed not in descriptor.optional_parameters()


def test_pattern_names_are_unique_and_aliases_resolve_to_canonicals() -> None:
    # Arrange.
    canonical = AgentPatternRegistry.canonical_names()

    # Assert: one row per name, and every advertised name resolves.
    assert len(set(canonical)) == len(canonical)
    for name in AgentPatternRegistry.pattern_names():
        assert AgentPatternRegistry.descriptor(name).name in canonical


# --- laziness -------------------------------------------------------------


def test_listing_and_resolving_names_never_touches_the_classes() -> None:
    """A row is data until asked for the class — that is what keeps it a table."""
    # Arrange: a row whose target could not possibly import.
    bogus = PatternDescriptor("bogus", "pirn_agents.no_such_module:Nope", "query")

    # Act / Assert: everything name-shaped works.
    assert bogus.name == "bogus"
    assert bogus.module_name == "pirn_agents.no_such_module"
    assert bogus.class_name == "Nope"

    # Assert: only asking for the class fails, and it says which row.
    with pytest.raises(ModuleNotFoundError):
        bogus.knot_class()


def test_a_row_pointing_at_a_non_pipeline_is_rejected_on_resolution() -> None:
    # Arrange: a real class that is not a SubTapestry.
    bad = PatternDescriptor("bad", "pirn_agents.builder.agent:Agent", "query")

    # Act / Assert.
    with pytest.raises(TypeError, match="must be a SubTapestry subclass"):
        bad.knot_class()


def test_a_row_declaring_a_seed_the_class_lacks_is_rejected() -> None:
    # Arrange: right class, wrong seed parameter.
    wrong = PatternDescriptor(
        "wrong", "pirn_agents.specializations.rag.naive_rag_pipeline:NaiveRAGPipeline", "prompt"
    )

    # Act / Assert: the row is checked against the constructor it names.
    with pytest.raises(ValueError, match="is not a constructor parameter"):
        wrong.knot_class()
