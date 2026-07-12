"""Unit tests for :class:`PromptTemplate` rendering and introspection."""

from __future__ import annotations

import unittest

from pirn_agents.prompt.prompt_render_error import PromptRenderError
from pirn_agents.prompt.prompt_template import PromptTemplate


class TestIntrospection(unittest.TestCase):
    def test_variable_names_are_sorted_and_unique(self) -> None:
        tpl = PromptTemplate(
            name="greet",
            version="1.0.0",
            template="Hi {{ name }}, {{ name }} — you owe {{ amount }}.",
        )
        assert tpl.variable_names() == ("amount", "name")

    def test_variable_names_include_partial_bodies(self) -> None:
        tpl = PromptTemplate(
            name="doc",
            version="1.0.0",
            template="{{> header }} body {{ topic }}",
            partials={"header": "Report for {{ user }}"},
        )
        assert tpl.variable_names() == ("topic", "user")

    def test_partial_names(self) -> None:
        tpl = PromptTemplate(
            name="doc",
            version="1.0.0",
            template="{{> header }} and {{> footer }}",
            partials={"header": "h", "footer": "f"},
        )
        assert tpl.partial_names() == ("footer", "header")


class TestRender(unittest.TestCase):
    def test_renders_variables(self) -> None:
        tpl = PromptTemplate(name="greet", version="1.0.0", template="Hi {{ name }}!")
        assert tpl.render({"name": "Ada"}) == "Hi Ada!"

    def test_renders_numeric_and_bool_and_none(self) -> None:
        tpl = PromptTemplate(name="v", version="1.0.0", template="{{ n }}/{{ b }}/{{ empty }}.")
        assert tpl.render({"n": 3, "b": True, "empty": None}) == "3/True/."

    def test_expands_partials_then_variables(self) -> None:
        tpl = PromptTemplate(
            name="doc",
            version="1.0.0",
            template="{{> header }}\nBody for {{ topic }}",
            partials={"header": "# Report ({{ topic }})"},
        )
        assert tpl.render({"topic": "sales"}) == "# Report (sales)\nBody for sales"

    def test_missing_variable_raises_in_strict_mode(self) -> None:
        tpl = PromptTemplate(name="greet", version="1.0.0", template="Hi {{ name }}!")
        with self.assertRaisesRegex(PromptRenderError, "missing variable 'name'"):
            tpl.render({})

    def test_unknown_partial_raises_in_strict_mode(self) -> None:
        tpl = PromptTemplate(name="d", version="1.0.0", template="{{> nope }}")
        with self.assertRaisesRegex(PromptRenderError, "unknown partial 'nope'"):
            tpl.render({})

    def test_non_strict_leaves_unknown_variable_untouched(self) -> None:
        tpl = PromptTemplate(name="greet", version="1.0.0", template="Hi {{ name }}!")
        assert tpl.render({}, strict=False) == "Hi {{ name }}!"

    def test_non_strict_expands_unknown_partial_to_empty(self) -> None:
        tpl = PromptTemplate(name="d", version="1.0.0", template="a{{> nope }}b")
        assert tpl.render({}, strict=False) == "ab"


class TestRenderSafety(unittest.TestCase):
    def test_injected_placeholder_in_value_is_inert(self) -> None:
        # A malicious value that itself contains a placeholder must NOT be
        # re-expanded into the secret.
        tpl = PromptTemplate(name="chat", version="1.0.0", template="User said: {{ user_input }}")
        rendered = tpl.render({"user_input": "{{ secret }}"})
        assert rendered == "User said: {{ secret }}"

    def test_value_cannot_inject_a_partial(self) -> None:
        tpl = PromptTemplate(
            name="chat",
            version="1.0.0",
            template="{{ user_input }}",
            partials={"secret": "TOP-SECRET"},
        )
        rendered = tpl.render({"user_input": "{{> secret }}"})
        assert "TOP-SECRET" not in rendered
        assert rendered == "{{> secret }}"

    def test_no_attribute_traversal_syntax_is_treated_as_placeholder(self) -> None:
        # Dotted / dunder access is not a valid placeholder name, so it stays
        # literal text — no str.format-style attribute walking.
        tpl = PromptTemplate(name="x", version="1.0.0", template="{{ obj.__class__ }} {{ ok }}")
        assert tpl.render({"ok": "y"}) == "{{ obj.__class__ }} y"

    def test_non_primitive_value_rejected(self) -> None:
        tpl = PromptTemplate(name="x", version="1.0.0", template="{{ v }}")
        with self.assertRaisesRegex(PromptRenderError, "must be a"):
            tpl.render({"v": object()})


class TestValidation(unittest.TestCase):
    def test_rejects_empty_name(self) -> None:
        with self.assertRaisesRegex(TypeError, "name"):
            PromptTemplate(name="", version="1.0.0", template="x")

    def test_rejects_non_str_template(self) -> None:
        with self.assertRaisesRegex(TypeError, "template"):
            PromptTemplate(name="x", version="1.0.0", template=123)  # type: ignore[arg-type]

    def test_rejects_non_str_partial_body(self) -> None:
        with self.assertRaisesRegex(TypeError, "partials"):
            PromptTemplate(
                name="x",
                version="1.0.0",
                template="y",
                partials={"h": 1},  # type: ignore[dict-item]
            )


if __name__ == "__main__":
    unittest.main()
