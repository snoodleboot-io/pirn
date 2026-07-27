"""End-to-end tests that ``specializations/rag`` prompts are operator-tunable.

The pins in ``test_rag_prompt_pins.py`` prove the conversion changed no delivered
text. These prove the conversion bought something: a loaded prompt pack retunes a
shipped RAG prompt with no code change, slot values still reach the rewritten
text, and the one prompt exposed as a constructor parameter resolves its default
when the knot is *built* rather than when its signature is evaluated at import.
"""

from __future__ import annotations

import inspect
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.prompt.prompt_catalog import PromptCatalog
from pirn_agents.specializations.rag.rag_prompt_builder import RAGPromptBuilder
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn_agents.specializations.rag.sub_question_decomposer import SubQuestionDecomposer

from tests.specializations.conftest import StubLLMProvider


class _SharedCatalogCase(unittest.IsolatedAsyncioTestCase):
    """Base case that keeps the process-wide catalog out of other tests."""

    def setUp(self) -> None:
        PromptCatalog.reset_shared()

    def tearDown(self) -> None:
        PromptCatalog.reset_shared()

    @staticmethod
    def _load(name: str, body: str) -> None:
        PromptCatalog.shared().load_mapping({"templates": {name: body}})


class PackRetunesRagPromptTests(_SharedCatalogCase):
    """A loaded pack retunes a shipped RAG prompt without touching Python."""

    async def test_pack_replaces_a_whole_prompt(self) -> None:
        self._load(
            "specializations.rag.rag_synthesizer.synthesis_prompt",
            "Answer in French.\n\n{{ query }}\n{{ context }}",
        )
        llm = StubLLMProvider(["answer"])
        knot = RAGSynthesizer(query="Q", documents=[], llm=llm, _config=KnotConfig(id="synth"))
        await knot.process(query="Q", documents=[{"text": "S"}], llm=llm)
        assert llm.calls[0][0]["content"] == "Answer in French.\n\nQ\n[1] S"

    async def test_pack_may_drop_every_slot(self) -> None:
        self._load(
            "specializations.rag.sub_question_decomposer.decomposition_prompt",
            "List the sub-questions.",
        )
        llm = StubLLMProvider(["s1"])
        knot = SubQuestionDecomposer(query="Q", llm=llm, _config=KnotConfig(id="decompose"))
        await knot.process(query="Q", llm=llm, max_sub_questions=2)
        assert llm.calls[0][0]["content"] == "List the sub-questions."

    async def test_slot_the_call_site_cannot_supply_stays_literal(self) -> None:
        self._load(
            "specializations.rag.sub_question_decomposer.decomposition_prompt",
            "Split {{ query }} using {{ nonexistent }}.",
        )
        llm = StubLLMProvider(["s1"])
        knot = SubQuestionDecomposer(query="Q", llm=llm, _config=KnotConfig(id="decompose"))
        await knot.process(query="Q", llm=llm, max_sub_questions=2)
        assert llm.calls[0][0]["content"] == "Split Q using {{ nonexistent }}."


class ParameterDefaultResolvesAtCallTimeTests(_SharedCatalogCase):
    """``RAGPromptBuilder.instruction`` binds at construction, not at import."""

    def test_signature_default_is_none_not_a_binding(self) -> None:
        default = inspect.signature(RAGPromptBuilder.__init__).parameters["instruction"].default
        assert default is None

    async def test_pack_loaded_after_import_still_wins(self) -> None:
        self._load(
            "specializations.rag.rag_prompt_builder.instruction",
            "Use only the sub-graph.",
        )
        with Tapestry() as tapestry:
            RAGPromptBuilder(query="Q", retrieved=[], _config=KnotConfig(id="prompt"))
        result = await tapestry.run(RunRequest())
        assert result.outputs["prompt"] == (
            "Use only the sub-graph.\n\nContext:\n(no context retrieved)\n\nQuestion: Q\nAnswer:"
        )

    async def test_explicit_instruction_beats_the_pack(self) -> None:
        self._load(
            "specializations.rag.rag_prompt_builder.instruction",
            "Use only the sub-graph.",
        )
        with Tapestry() as tapestry:
            RAGPromptBuilder(
                query="Q",
                retrieved=[],
                instruction="Caller wins.",
                _config=KnotConfig(id="prompt"),
            )
        result = await tapestry.run(RunRequest())
        assert result.outputs["prompt"].startswith("Caller wins.\n\nContext:\n")

    async def test_resolved_instruction_reaches_process_as_a_string(self) -> None:
        with Tapestry() as tapestry:
            RAGPromptBuilder(query="Q", retrieved=[], _config=KnotConfig(id="prompt"))
        result = await tapestry.run(RunRequest())
        assert isinstance(result.outputs["prompt"], str)
        assert "PromptBinding" not in result.outputs["prompt"]


class RagPromptRenderTests(_SharedCatalogCase):
    """``PromptBinding.render`` never re-scans what it inserts, from a RAG call site.

    The rag-local ``RagPrompt`` helper these cases were first written against was
    folded into :meth:`PromptBinding.render` once both prompt lanes had landed —
    the concern was never rag-specific. Its input guard went with it: ``render``
    is a method on the binding, so there is no longer a non-binding to reject.
    """

    def test_a_value_containing_a_slot_marker_is_inert(self) -> None:
        binding = PromptBinding(name="test.inert", default="Q: {{ query }}")
        assert binding.render({"query": "{{ secret }}"}) == "Q: {{ secret }}"

    def test_an_explicit_catalog_is_consulted_instead_of_the_shared_one(self) -> None:
        binding = PromptBinding(name="test.scoped", default="built-in {{ query }}")
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"test.scoped": "scoped {{ query }}"}})
        assert binding.render({"query": "Q"}, catalog=catalog) == "scoped Q"
        assert binding.render({"query": "Q"}) == "built-in Q"
