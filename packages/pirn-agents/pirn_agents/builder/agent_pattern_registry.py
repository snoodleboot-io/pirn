"""``AgentPatternRegistry`` — the table of every shipped agentic pattern.

This registry is the single place that knows how a named pattern (``"react"``,
``"graph_rag"``, ``"debate"``) maps onto a concrete
:class:`~pirn.nodes.sub_tapestry.SubTapestry` subclass, and how the builder's
collected components and options are bound to that class's constructor.

Every pattern under ``specializations/`` is listed here (PIR-730). Before that,
three names were reachable through the facade and the rest only by importing and
hand-wiring the class — the builder advertised a breadth it did not have.
``tests/builder/test_pattern_registry_coverage.py`` now fails if a new pipeline
lands unregistered, so the table cannot silently fall behind again.

Binding is **derived, not restated**. Each row names the class and which
constructor parameter takes the runtime seed; which components are required and
which knobs are accepted come from the constructor signature itself (see
:class:`~pirn_agents.builder.pattern_descriptor.PatternDescriptor`). One binding
rule therefore serves all patterns, in place of a bespoke ``_build_x`` method per
pattern — and a pipeline that gains a required argument gains a required
component here with no edit.

The classes remain directly usable by hand; the registry adds no capability of
its own, and resolves a pattern's class only when that pattern is named.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.builder.pattern_descriptor import PatternDescriptor
from pirn_agents.builder.pattern_seed_kind import PatternSeedKind
from pirn_agents.types.messaging.agent_message import AgentMessage

_SPEC = "pirn_agents.specializations"
_MESSAGES = PatternSeedKind.MESSAGES

#: The pattern table: (name, "module:Class", seed parameter[, seed kind]).
#:
#: The seed is the constructor parameter the builder's ``.input(...)`` feeds —
#: by convention a pipeline's first parameter, the subject it acts on. Every
#: other required parameter is a component the caller supplies by name.
_PATTERNS: tuple[PatternDescriptor, ...] = (
    # --- document processing
    PatternDescriptor(
        "document_ingestion",
        f"{_SPEC}.document_processing.document_ingestion_pipeline:DocumentIngestionPipeline",
        "source",
    ),
    # Deviates from first-parameter: for QA the *question* is what varies per
    # run, while `source` is configuration, so the question is the seed.
    PatternDescriptor(
        "document_qa",
        f"{_SPEC}.document_processing.document_qa_pipeline:DocumentQAPipeline",
        "question",
    ),
    PatternDescriptor(
        "document_summarizer",
        f"{_SPEC}.document_processing.document_summarizer_pipeline:DocumentSummarizerPipeline",
        "source",
    ),
    PatternDescriptor(
        "document_translation",
        f"{_SPEC}.document_processing.document_translation_pipeline:DocumentTranslationPipeline",
        "source",
    ),
    PatternDescriptor(
        "ingestion",
        f"{_SPEC}.document_processing.ingestion_pipeline:IngestionPipeline",
        "source_connector",
    ),
    # --- evaluator / optimizer
    PatternDescriptor(
        "evaluator_optimizer",
        f"{_SPEC}.evaluator_optimizer.evaluator_optimizer_pipeline:EvaluatorOptimizerPipeline",
        "task",
    ),
    # --- guardrails
    PatternDescriptor(
        "fact_check", f"{_SPEC}.guardrails.fact_check_gate:FactCheckGate", "response"
    ),
    PatternDescriptor(
        "input_guardrail",
        f"{_SPEC}.guardrails.input_guardrail_gate:InputGuardrailGate",
        "messages",
        _MESSAGES,
    ),
    PatternDescriptor(
        "output_guardrail",
        f"{_SPEC}.guardrails.output_guardrail_gate:OutputGuardrailGate",
        "response",
    ),
    PatternDescriptor(
        "pii_redactor", f"{_SPEC}.guardrails.pii_redactor_check:PiiRedactorCheck", "response"
    ),
    # --- search
    PatternDescriptor("lats", f"{_SPEC}.lats.lats_search:LatsSearch", "task"),
    # --- multi-agent
    PatternDescriptor(
        "consensus", f"{_SPEC}.multi_agent.consensus_aggregator:ConsensusAggregator", "responses"
    ),
    PatternDescriptor("debate", f"{_SPEC}.multi_agent.debate_framework:DebateFramework", "topic"),
    PatternDescriptor(
        "orchestrator", f"{_SPEC}.multi_agent.orchestrator_agent:OrchestratorAgent", "task"
    ),
    PatternDescriptor(
        "orchestrator_workers",
        f"{_SPEC}.multi_agent.orchestrator_workers:OrchestratorWorkers",
        "tasks",
    ),
    PatternDescriptor(
        "parallel_specialists",
        f"{_SPEC}.multi_agent.parallel_specialist_fan_out:ParallelSpecialistFanOut",
        "task",
    ),
    PatternDescriptor(
        "round_robin_review",
        f"{_SPEC}.multi_agent.round_robin_review:RoundRobinReview",
        "response",
    ),
    # --- planning
    PatternDescriptor(
        "plan_react", f"{_SPEC}.plan_react.plan_react_pipeline:PlanReActPipeline", "task"
    ),
    PatternDescriptor(
        "prompt_chain",
        f"{_SPEC}.prompt_chaining.prompt_chain_pipeline:PromptChainPipeline",
        "task",
    ),
    # --- retrieval-augmented generation
    PatternDescriptor(
        "adaptive_rag", f"{_SPEC}.rag.adaptive_rag_pipeline:AdaptiveRAGPipeline", "query"
    ),
    PatternDescriptor(
        "agentic_rag", f"{_SPEC}.rag.agentic_rag_pipeline:AgenticRagPipeline", "query"
    ),
    PatternDescriptor(
        "contextual_retrieval",
        f"{_SPEC}.rag.contextual_retrieval_pipeline:ContextualRetrievalPipeline",
        "query",
    ),
    PatternDescriptor(
        "corrective_rag", f"{_SPEC}.rag.corrective_rag_pipeline:CorrectiveRAGPipeline", "query"
    ),
    PatternDescriptor(
        "flare_rag", f"{_SPEC}.rag.flare_active_rag_pipeline:FlareActiveRagPipeline", "query"
    ),
    PatternDescriptor("graph_rag", f"{_SPEC}.rag.graph_rag_pipeline:GraphRAGPipeline", "query"),
    PatternDescriptor("hyde_rag", f"{_SPEC}.rag.hyde_rag_pipeline:HyDERAGPipeline", "query"),
    PatternDescriptor(
        "multi_hop_rag", f"{_SPEC}.rag.multi_hop_rag_pipeline:MultiHopRAGPipeline", "query"
    ),
    PatternDescriptor("naive_rag", f"{_SPEC}.rag.naive_rag_pipeline:NaiveRAGPipeline", "query"),
    PatternDescriptor("rag_fusion", f"{_SPEC}.rag.rag_fusion_pipeline:RagFusionPipeline", "query"),
    PatternDescriptor("router_rag", f"{_SPEC}.rag.router_rag_pipeline:RouterRagPipeline", "query"),
    PatternDescriptor(
        "self_query_rag", f"{_SPEC}.rag.self_query_rag_pipeline:SelfQueryRagPipeline", "query"
    ),
    PatternDescriptor("self_rag", f"{_SPEC}.rag.self_rag_pipeline:SelfRAGPipeline", "query"),
    PatternDescriptor(
        "speculative_rag", f"{_SPEC}.rag.speculative_rag_pipeline:SpeculativeRagPipeline", "query"
    ),
    PatternDescriptor(
        "sub_question_rag", f"{_SPEC}.rag.sub_question_rag_pipeline:SubQuestionRagPipeline", "query"
    ),
    # --- indexing
    PatternDescriptor(
        "auto_merging_ingestor",
        f"{_SPEC}.rag.indexing.auto_merging_ingestor:AutoMergingIngestor",
        "text",
    ),
    PatternDescriptor(
        "parent_document_ingestor",
        f"{_SPEC}.rag.indexing.parent_document_ingestor:ParentDocumentIngestor",
        "text",
    ),
    PatternDescriptor(
        "raptor_tree_builder",
        f"{_SPEC}.rag.indexing.raptor_tree_builder:RaptorTreeBuilder",
        "text",
    ),
    # --- reasoning loops
    PatternDescriptor("react", f"{_SPEC}.react.react_loop:ReActLoop", "messages", _MESSAGES),
    PatternDescriptor(
        "reflexion", f"{_SPEC}.reflexion.reflexion_pipeline:ReflexionPipeline", "task"
    ),
    PatternDescriptor("rewoo", f"{_SPEC}.rewoo.rewoo_pipeline:ReWooPipeline", "goal"),
    PatternDescriptor(
        "router_fallback",
        f"{_SPEC}.routing.router_fallback_pipeline:RouterFallbackPipeline",
        "candidates",
    ),
    PatternDescriptor("self_ask", f"{_SPEC}.self_ask.self_ask_pipeline:SelfAskPipeline", "task"),
    # --- specialized agents
    PatternDescriptor(
        "browser_agent", f"{_SPEC}.specialized_agents.browser_agent:BrowserAgent", "goal"
    ),
    PatternDescriptor("code_agent", f"{_SPEC}.specialized_agents.code_agent:CodeAgent", "task"),
    PatternDescriptor(
        "data_analyst_agent",
        f"{_SPEC}.specialized_agents.data_analyst_agent:DataAnalystAgent",
        "question",
    ),
    PatternDescriptor(
        "research_agent", f"{_SPEC}.specialized_agents.research_agent:ResearchAgent", "topic"
    ),
    PatternDescriptor("sql_agent", f"{_SPEC}.specialized_agents.sql_agent:SQLAgent", "question"),
    # --- structured output
    PatternDescriptor(
        "enum_classifier",
        f"{_SPEC}.structured_output.enum_classifier_pipeline:EnumClassifierPipeline",
        "prompt",
    ),
    PatternDescriptor(
        "json_extractor",
        f"{_SPEC}.structured_output.json_extractor_pipeline:JsonExtractorPipeline",
        "prompt",
    ),
    PatternDescriptor(
        "pydantic_validator",
        f"{_SPEC}.structured_output.pydantic_validator_pipeline:PydanticValidatorPipeline",
        "prompt",
    ),
    PatternDescriptor(
        "retry_on_parse_failure",
        f"{_SPEC}.structured_output.retry_on_parse_failure:RetryOnParseFailure",
        "prompt",
    ),
    PatternDescriptor(
        "yaml_extractor",
        f"{_SPEC}.structured_output.yaml_extractor_pipeline:YamlExtractorPipeline",
        "prompt",
    ),
)

#: Convenience spellings that resolve to a canonical pattern name.
_ALIASES: Mapping[str, str] = {"rag": "naive_rag"}


class AgentPatternRegistry:
    """Resolves pattern names to :class:`SubTapestry` subclasses and builds them."""

    @classmethod
    def _descriptors(cls) -> Mapping[str, PatternDescriptor]:
        """Return the canonical name-to-descriptor table."""
        return {descriptor.name: descriptor for descriptor in _PATTERNS}

    @classmethod
    def pattern_names(cls) -> tuple[str, ...]:
        """Return the sorted, supported pattern names (including aliases)."""
        return tuple(sorted({*cls._descriptors(), *_ALIASES}))

    @classmethod
    def canonical_names(cls) -> tuple[str, ...]:
        """Return the sorted pattern names excluding aliases (one per class)."""
        return tuple(sorted(cls._descriptors()))

    @classmethod
    def descriptor(cls, pattern: str) -> PatternDescriptor:
        """Return the :class:`PatternDescriptor` for ``pattern``.

        Resolves aliases. Performs no import — use :meth:`pattern_class` (or the
        descriptor's own accessors) when the class itself is needed.

        Raises:
            ValueError: If ``pattern`` is unknown.
        """
        table = cls._descriptors()
        resolved = table.get(_ALIASES.get(pattern, pattern))
        if resolved is None:
            raise ValueError(
                f"AgentPatternRegistry: unknown pattern {pattern!r}; "
                f"known patterns are {list(cls.pattern_names())!r}"
            )
        return resolved

    @classmethod
    def pattern_class(cls, pattern: str) -> type[SubTapestry]:
        """Return the :class:`SubTapestry` subclass a pattern name maps to.

        Raises:
            ValueError: If ``pattern`` is unknown.
        """
        return cls.descriptor(pattern).knot_class()

    @classmethod
    def required_components(cls, pattern: str) -> tuple[str, ...]:
        """Return the component names ``pattern`` cannot be built without.

        Raises:
            ValueError: If ``pattern`` is unknown.
        """
        return cls.descriptor(pattern).required_components()

    @classmethod
    def optional_parameters(cls, pattern: str) -> tuple[str, ...]:
        """Return the option names ``pattern`` accepts (all have defaults).

        Raises:
            ValueError: If ``pattern`` is unknown.
        """
        return cls.descriptor(pattern).optional_parameters()

    @classmethod
    def describe(cls, pattern: str) -> dict[str, Any]:
        """Return a printable summary of ``pattern``'s build contract.

        Raises:
            ValueError: If ``pattern`` is unknown.
        """
        return cls.descriptor(pattern).describe()

    @classmethod
    def build(
        cls,
        pattern: str,
        *,
        knot_id: str,
        input_value: Any,
        components: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> SubTapestry:
        """Construct the pattern's :class:`SubTapestry` from resolved parts.

        Args:
            pattern: The agentic pattern name (or alias).
            knot_id: Stable id for the generated top-level knot.
            input_value: The runtime seed, bound to the pattern's seed parameter.
            components: Live objects keyed by constructor parameter name — the
                LLM provider, memory store, embedder, tools, specialists, and
                whatever else the chosen pattern requires. See
                :meth:`required_components`.
            options: Scalar knobs keyed by constructor parameter name, each of
                which has a default. See :meth:`optional_parameters`.

        Returns:
            A constructed :class:`SubTapestry` equivalent to hand-wiring the
            corresponding pattern class.

        Raises:
            ValueError: If ``pattern`` is unknown, a required component is
                missing, or a supplied name is not a parameter of this pattern.
            TypeError: If the seed cannot be coerced to the shape the pattern
                takes.
        """
        descriptor = cls.descriptor(pattern)
        supplied_components = dict(components or {})
        supplied_options = dict(options or {})
        cls._reject_unknown(descriptor, supplied_components, supplied_options)

        bound: dict[str, Any] = {descriptor.seed: cls._coerce_seed(descriptor, input_value)}
        missing: list[str] = []
        for name in descriptor.required_components():
            if name in supplied_components:
                bound[name] = supplied_components[name]
            elif name in supplied_options:
                bound[name] = supplied_options[name]
            else:
                missing.append(name)
        if missing:
            raise ValueError(
                f"AgentPatternRegistry: pattern {descriptor.name!r} requires "
                f"{missing!r}; supply them with .component(name, value)"
            )
        for name in descriptor.optional_parameters():
            if name in supplied_components:
                bound[name] = supplied_components[name]
            elif name in supplied_options:
                bound[name] = supplied_options[name]

        knot_class = descriptor.knot_class()
        return knot_class(_config=KnotConfig(id=knot_id), **bound)

    @classmethod
    def _reject_unknown(
        cls,
        descriptor: PatternDescriptor,
        components: Mapping[str, Any],
        options: Mapping[str, Any],
    ) -> None:
        """Fail on any supplied name the pattern's constructor does not take.

        A silently ignored ``llm=`` or a mistyped option is worse than a build
        error: the graph is wired differently from what was asked for, and
        nothing says so.

        Raises:
            ValueError: If a component or option is not a parameter of the
                pattern, or collides with the seed.
        """
        for label, supplied in (("component", components), ("option", options)):
            for name in supplied:
                if name == descriptor.seed:
                    raise ValueError(
                        f"AgentPatternRegistry: {label} {name!r} is pattern "
                        f"{descriptor.name!r}'s input seed; set it with .input(...)"
                    )
                if not descriptor.accepts(name):
                    raise ValueError(
                        f"AgentPatternRegistry: pattern {descriptor.name!r} takes no "
                        f"{label} {name!r}; it accepts components "
                        f"{list(descriptor.required_components())!r} and options "
                        f"{list(descriptor.optional_parameters())!r}"
                    )

    @classmethod
    def _coerce_seed(cls, descriptor: PatternDescriptor, input_value: Any) -> Any:
        """Return ``input_value`` in the shape the pattern's seed parameter takes."""
        if descriptor.seed_kind is PatternSeedKind.MESSAGES:
            return cls._normalise_messages(input_value)
        return input_value

    @classmethod
    def _normalise_messages(cls, input_value: Any) -> tuple[AgentMessage, ...]:
        """Coerce a builder input into a tuple of :class:`AgentMessage`.

        A bare string becomes a single ``user`` message; a sequence of
        :class:`AgentMessage` is passed through as a tuple.

        Raises:
            TypeError: If ``input_value`` is neither a string nor a sequence of
                :class:`AgentMessage`.
        """
        if isinstance(input_value, str):
            return (AgentMessage(role="user", content=input_value),)
        if isinstance(input_value, AgentMessage):
            return (input_value,)
        if isinstance(input_value, Sequence):
            messages = tuple(input_value)
            for index, message in enumerate(messages):
                if not isinstance(message, AgentMessage):
                    raise TypeError(
                        f"AgentPatternRegistry: input[{index}] must be an AgentMessage, "
                        f"got {type(message).__name__}"
                    )
            return messages
        raise TypeError(
            "AgentPatternRegistry: this pattern's input must be a str or a sequence of "
            f"AgentMessage, got {type(input_value).__name__}"
        )
