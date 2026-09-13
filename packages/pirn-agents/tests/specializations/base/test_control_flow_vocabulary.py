"""Guard: control-flow vocabulary bypasses (ADR agents-speaks-core WS5a).

Sibling to ``test_no_engine_bypass.py``, reusing its walk
(``BypassInventory.discover_process_methods``) and its exact-equality
allowlist discipline, for three shapes that ratchet does not cover:

(a) A ``Source`` subclass **defined** inside a ``process()`` body, whether or
    not it is the value returned. ``pirn.core.parameter.Parameter`` is the
    core primitive for "make an already-resolved value visible as a graph
    node" — a bespoke ``Source`` closure re-invents it every time (see
    ``evaluator_optimizer_pipeline.py:109`` for the sanctioned form). Broader
    than ``test_no_engine_bypass.py``'s ``RETURNS_INLINE_SOURCE``, which only
    fires when the inline class is the returned sink.

(b) An "identity knot": a ``process()`` whose only statement returns one of
    its own inputs unchanged. Some of these are legitimate — a Rule 6
    (``docs/contributing/knot-design-rules.md``) *vending Knot* for an opaque,
    non-serialisable resource (a pooled HTTP client, an LLM provider, a vector
    store handle) has exactly this shape by design, and stays in the frozen
    list permanently. The rest (``ResolvedValueKnot``, ``_ResponseEcho``) wrap
    an ordinary, already-known *value* — that is ``Parameter``'s job, not a
    bespoke pass-through class.

(c) ``AgentPipeline.process()`` annotated ``-> Any``. The ``SubTapestry``
    contract (enforced at runtime by ``SubTapestry.__call__``) already
    requires ``process()`` to return a ``Knot``; ``-> Any`` just hides that
    from readers and from pyright.

Same ratchet discipline as the sibling file: allowlists are asserted by
**exact equality**. Adding a new instance fails because it is not in the
list; fixing one without deleting its line also fails, so the list cannot
rot into a lie.
"""

from __future__ import annotations

import ast
import unittest

from tests.specializations.base.bypass_inventory import BypassInventory

# --- known bypasses, frozen (ADR agents-speaks-core WS5a) ------------------

#: A `Source` subclass defined anywhere inside `process()`, not only ones
#: that are returned. Nine remain (down from twelve): all exist to
#: re-inject an already-resolved value into the inner graph — the
#: `Parameter` use case. `RetryOnParseFailure` is fixed — see its
#: `_RetryResultExtractor`/`_RetryOnParseFailureLoop` (ADR agents-speaks-core
#: WS5a). `SelfAskPipeline` is fixed — see its `_SelfAskComposer`/
#: `_SelfAskLoop`; `PromptChainPipeline` is fixed — see its
#: `_PromptChainResultExtractor`/`_PromptChainLoop` (ADR agents-speaks-core
#: WS5b).
DEFINES_INLINE_SOURCE = frozenset(
    {
        "specializations/lats/lats_search.py::LatsSearch",
        "specializations/multi_agent/orchestrator_agent.py::OrchestratorAgent",
        "specializations/plan_react/plan_react_pipeline.py::PlanReActPipeline",
        "specializations/rag/flare_active_rag_pipeline.py::FlareActiveRagPipeline",
        "specializations/rag/multi_hop_rag_pipeline.py::MultiHopRAGPipeline",
        "specializations/reflexion/reflexion_pipeline.py::ReflexionPipeline",
        "specializations/structured_output/json_extractor_pipeline.py::JsonExtractorPipeline",
        "specializations/structured_output/pydantic_validator_pipeline.py::PydanticValidatorPipeline",
        "specializations/structured_output/yaml_extractor_pipeline.py::YamlExtractorPipeline",
    }
)

#: `process()` bodies that return one of their own inputs unchanged.
#: Permanent members (Rule 6 vending Knots — legitimate, not a bypass):
#: HttpConnectorKnot, SearchConnectorKnot, SqlConnectorKnot, LLMProviderKnot,
#: MemoryStoreKnot, EmbeddingProviderKnot, VectorStoreKnot, ToolClientKnot —
#: each smuggles a non-serialisable, already-constructed resource through the
#: graph exactly once, which `Parameter` cannot do (`Parameter` validates its
#: value with a Pydantic `TypeAdapter` and is a graph ROOT — a vending Knot's
#: `Knot | Resource` input can also be wired to an upstream knot, which
#: `Parameter` structurally cannot accept). `_ResponseEcho` is pinned
#: importable and explicitly documented as "not a transform — do not fix, do
#: not delete" (`_response_echo.py`); it stays for that reason, not because
#: it is legitimate the way the vending Knots are. `ResolvedValueKnot` was the
#: burn-down target here — it wrapped an ordinary already-known value, not an
#: opaque resource — and is now a `Parameter` deprecation shim: its `process()`
#: is inherited from `Parameter` rather than redefined, so it no longer
#: appears in this walk at all.
IS_IDENTITY_KNOT = frozenset(
    {
        "connectors/knots/http_connector_knot.py::HttpConnectorKnot",
        "connectors/knots/search_connector_knot.py::SearchConnectorKnot",
        "connectors/knots/sql_connector_knot.py::SqlConnectorKnot",
        "llm/knots/llm_provider_knot.py::LLMProviderKnot",
        "memory/stores/knots/memory_store_knot.py::MemoryStoreKnot",
        "retrieval/embeddings/knots/embedding_provider_knot.py::EmbeddingProviderKnot",
        "retrieval/vector_stores/knots/vector_store_knot.py::VectorStoreKnot",
        "specializations/multi_agent/_response_echo.py::_ResponseEcho",
        "tools/knots/tool_client_knot.py::ToolClientKnot",
    }
)

#: `AgentPipeline.process()` annotated `-> Any` instead of `-> Knot`. Empty:
#: WS5a annotated all 47 as `-> Knot` in the same PR that added this ratchet,
#: so this list documents the contract rather than tracking a backlog. Kept
#: as an assertion (not deleted) so a future `-> Any` regresses loudly.
PROCESS_RETURNS_ANY: frozenset[str] = frozenset()


class TestControlFlowVocabularyBypass(unittest.TestCase):
    """Freeze the WS5a bypass inventory. Exact equality in both directions."""

    def setUp(self) -> None:
        self.pipelines = BypassInventory.discover_process_methods()
        self.agent_pipelines = BypassInventory.discover_agent_pipeline_process_methods()

    def test_the_walks_are_not_vacuous(self) -> None:
        assert len(self.pipelines) >= 200, len(self.pipelines)
        assert len(self.agent_pipelines) >= 50, len(self.agent_pipelines)

    def test_inline_source_definitions_are_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.defines_inline_source(proc)
        }
        assert found == DEFINES_INLINE_SOURCE, {
            "new": sorted(found - DEFINES_INLINE_SOURCE),
            "fixed — remove from DEFINES_INLINE_SOURCE": sorted(DEFINES_INLINE_SOURCE - found),
        }

    def test_identity_knots_are_frozen(self) -> None:
        found = {
            label
            for label, proc in self.pipelines.items()
            if BypassInventory.is_identity_knot(proc)
        }
        assert found == IS_IDENTITY_KNOT, {
            "new": sorted(found - IS_IDENTITY_KNOT),
            "fixed — remove from IS_IDENTITY_KNOT": sorted(IS_IDENTITY_KNOT - found),
        }

    def test_process_returns_any_is_frozen(self) -> None:
        found = {
            label
            for label, proc in self.agent_pipelines.items()
            if BypassInventory.process_returns_any(proc)
        }
        assert found == PROCESS_RETURNS_ANY, {
            "new": sorted(found - PROCESS_RETURNS_ANY),
            "fixed — remove from PROCESS_RETURNS_ANY": sorted(PROCESS_RETURNS_ANY - found),
        }


class TestDetectorsAreDiscriminating(unittest.TestCase):
    """The detectors must fire on the shapes they name, and not on clean code."""

    @staticmethod
    def _process_of(source: str) -> ast.AST:
        tree = ast.parse(source)
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        return next(
            n
            for n in cls.body
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "process"
        )

    def test_clean_pipeline_trips_nothing(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, x, **_) -> Knot:\n"
            "        a = Alpha(value=x, _config=KnotConfig(id='a'))\n"
            "        return Beta(source=a, _config=KnotConfig(id='b'))\n"
        )
        assert not BypassInventory.defines_inline_source(proc)
        assert not BypassInventory.is_identity_knot(proc)
        assert not BypassInventory.process_returns_any(proc)

    def test_inline_source_trips_even_when_not_returned(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        class _Seed(Source):\n"
            "            async def process(self, **_):\n"
            "                return 0\n"
            "        seed = _Seed(_config=KnotConfig(id='s'))\n"
            "        return Real(state=seed, _config=KnotConfig(id='r'))\n"
        )
        assert BypassInventory.defines_inline_source(proc)

    def test_non_source_inline_class_does_not_trip(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, **_):\n"
            "        class _Helper:\n"
            "            pass\n"
            "        return Real(_config=KnotConfig(id='r'))\n"
        )
        assert not BypassInventory.defines_inline_source(proc)

    def test_identity_return_trips(self) -> None:
        proc = self._process_of(
            "class P:\n    async def process(self, value, **_):\n        return value\n"
        )
        assert BypassInventory.is_identity_knot(proc)

    def test_identity_return_with_docstring_still_trips(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, value, **_):\n"
            "        'doc'\n"
            "        return value\n"
        )
        assert BypassInventory.is_identity_knot(proc)

    def test_transform_before_return_does_not_trip(self) -> None:
        proc = self._process_of(
            "class P:\n    async def process(self, value, **_):\n        return tuple(value)\n"
        )
        assert not BypassInventory.is_identity_knot(proc)

    def test_multi_statement_body_does_not_trip(self) -> None:
        proc = self._process_of(
            "class P:\n"
            "    async def process(self, value, **_):\n"
            "        logged = value\n"
            "        return logged\n"
        )
        assert not BypassInventory.is_identity_knot(proc)

    def test_bare_any_return_trips(self) -> None:
        proc = self._process_of("class P:\n    async def process(self, **_) -> Any:\n        ...\n")
        assert BypassInventory.process_returns_any(proc)

    def test_knot_return_does_not_trip(self) -> None:
        proc = self._process_of(
            "class P:\n    async def process(self, **_) -> Knot:\n        ...\n"
        )
        assert not BypassInventory.process_returns_any(proc)

    def test_missing_annotation_does_not_trip(self) -> None:
        proc = self._process_of("class P:\n    async def process(self, **_):\n        ...\n")
        assert not BypassInventory.process_returns_any(proc)


class TestAgentPipelineDiscoveryIsScoped(unittest.TestCase):
    """`discover_agent_pipeline_process_methods` must actually filter by base."""

    def test_finds_a_known_agent_pipeline(self) -> None:
        found = BypassInventory.discover_agent_pipeline_process_methods()
        assert "specializations/react/react_loop.py::ReActLoop" in found

    def test_excludes_non_agent_pipeline_knots(self) -> None:
        found = BypassInventory.discover_agent_pipeline_process_methods()
        assert "connectors/knots/http_connector_knot.py::HttpConnectorKnot" not in found
