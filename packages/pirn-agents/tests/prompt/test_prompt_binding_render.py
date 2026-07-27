"""Tests for :meth:`PromptBinding.render` — the slot-filling read path.

``resolve()`` returns prompt text verbatim, which is right for the static sites
but ships ``{{ slot }}`` markers to the model for any prompt that embeds runtime
data. ``render()`` closes that: it resolves, then substitutes once, non-strict.
The point of the single pass is that the built-in default and a loaded pack are
filled *identically* — ``resolve()`` consults the catalog with no variables, so a
registered body comes back with its markers still literal.
"""

from __future__ import annotations

import inspect
import unittest

from pirn_agents.memory.patterns.semantic_memory_pipeline import SemanticMemoryPipeline
from pirn_agents.memory.patterns.semantic_memory_upsert import SemanticMemoryUpsert
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.prompt.prompt_catalog import PromptCatalog
from pirn_agents.security.llm_injection_classifier import LlmInjectionClassifier
from pirn_agents.tools.retrieval.rag_tool import RagTool


class RenderFromBuiltinDefault(unittest.TestCase):
    """With nothing registered, slots are filled from the shipped literal."""

    def test_fills_every_supplied_slot(self) -> None:
        binding = PromptBinding(
            name="t.greet",
            default="Hello {{ name }}, welcome to {{ place }}.",
        )
        catalog = PromptCatalog()
        assert (
            binding.render({"name": "Ada", "place": "Bletchley"}, catalog=catalog)
            == "Hello Ada, welcome to Bletchley."
        )

    def test_repeated_slot_is_filled_every_time(self) -> None:
        binding = PromptBinding(name="t.lang", default="A {{ lang }} expert writing {{ lang }}.")
        assert (
            binding.render({"lang": "C++"}, catalog=PromptCatalog()) == "A C++ expert writing C++."
        )

    def test_unsupplied_slot_stays_literal_rather_than_raising(self) -> None:
        binding = PromptBinding(name="t.partial", default="{{ a }} and {{ b }}")
        assert binding.render({"a": "x"}, catalog=PromptCatalog()) == "x and {{ b }}"

    def test_slotless_default_is_unchanged(self) -> None:
        binding = PromptBinding(name="t.plain", default="Just text.")
        assert binding.render({"unused": "x"}, catalog=PromptCatalog()) == "Just text."

    def test_substituted_value_is_inert(self) -> None:
        """A value containing a marker cannot inject a slot — the pass never re-scans."""
        binding = PromptBinding(name="t.inert", default="{{ user }}")
        rendered = binding.render({"user": "{{ secret }}"}, catalog=PromptCatalog())
        assert rendered == "{{ secret }}"


class RenderFromLoadedPack(unittest.TestCase):
    """A loaded template is filled by the same pass, from the same values."""

    def test_pack_body_wins_and_its_slots_are_filled(self) -> None:
        binding = PromptBinding(name="t.greet", default="Hello {{ name }}.")
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"t.greet": "Bonjour {{ name }} !"}})
        assert binding.render({"name": "Ada"}, catalog=catalog) == "Bonjour Ada !"

    def test_pack_may_drop_a_slot_the_call_site_still_supplies(self) -> None:
        binding = PromptBinding(name="t.greet", default="Hello {{ name }}.")
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"t.greet": "Hello."}})
        assert binding.render({"name": "Ada"}, catalog=catalog) == "Hello."

    def test_pack_may_add_a_slot_the_default_never_had(self) -> None:
        binding = PromptBinding(name="t.greet", default="Hello {{ name }}.")
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"t.greet": "Hello {{ name }} from {{ name }}."}})
        assert binding.render({"name": "Ada"}, catalog=catalog) == "Hello Ada from Ada."


class RenderPrecedence(unittest.TestCase):
    """``render`` inherits ``resolve``'s precedence, then fills slots."""

    def test_declared_override_beats_the_pack_and_is_still_filled(self) -> None:
        binding = PromptBinding(name="t.greet", default="Hello {{ name }}.")
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"t.greet": "Bonjour {{ name }} !"}})
        assert binding.render({"name": "Ada"}, "Yo {{ name }}.", catalog=catalog) == "Yo Ada."

    def test_declared_equal_to_default_still_lets_the_pack_win(self) -> None:
        binding = PromptBinding(name="t.greet", default="Hello {{ name }}.")
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"t.greet": "Bonjour {{ name }} !"}})
        assert (
            binding.render({"name": "Ada"}, "Hello {{ name }}.", catalog=catalog) == "Bonjour Ada !"
        )

    def test_no_variables_renders_the_body_unchanged(self) -> None:
        binding = PromptBinding(name="t.plain", default="Static text.")
        assert binding.render(catalog=PromptCatalog()) == "Static text."


class ResolveKeepsStageABehaviour(unittest.TestCase):
    """``resolve`` must not have acquired slot filling — stage A relies on verbatim."""

    def test_default_is_returned_byte_for_byte_including_markers(self) -> None:
        binding = PromptBinding(name="t.greet", default="Hello {{ name }}.")
        assert binding.resolve(catalog=PromptCatalog()) == "Hello {{ name }}."

    def test_registered_body_comes_back_with_markers_literal(self) -> None:
        binding = PromptBinding(name="t.greet", default="Hello {{ name }}.")
        catalog = PromptCatalog()
        catalog.load_mapping({"templates": {"t.greet": "Bonjour {{ name }} !"}})
        assert binding.resolve(catalog=catalog) == "Bonjour {{ name }} !"


class NoBindingLeaksIntoASignature(unittest.TestCase):
    """A ``PromptBinding`` never reaches a caller where a ``str`` is expected."""

    def test_prompt_parameter_defaults_are_plain_strings_or_none(self) -> None:
        cases = (
            (SemanticMemoryPipeline.__init__, "fact_extraction_prompt"),
            (SemanticMemoryPipeline.process, "fact_extraction_prompt"),
            (SemanticMemoryUpsert.__init__, "fact_extraction_prompt"),
            (SemanticMemoryUpsert.process, "fact_extraction_prompt"),
            (LlmInjectionClassifier.__init__, "system_prompt"),
            (RagTool.__init__, "system_prompt"),
        )
        for func, parameter in cases:
            with self.subTest(func=func.__qualname__, parameter=parameter):
                default = inspect.signature(func).parameters[parameter].default
                assert not isinstance(default, PromptBinding)
                assert default is None or isinstance(default, str)
