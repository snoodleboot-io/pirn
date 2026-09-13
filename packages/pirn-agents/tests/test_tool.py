"""Unit tests for :class:`Tool` — a capability expressed as a ``Knot`` class (ADR WS1)."""

from __future__ import annotations

import unittest
import warnings
from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pydantic import Field

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_permissions import ToolPermissions


class Adder(Tool):
    """Add two integers.

    A second paragraph the model never sees.
    """

    tool_name: ClassVar[str] = "adder"
    permissions: ClassVar[ToolPermissions] = ToolPermissions(approval_required=True)

    def __init__(
        self,
        *,
        left: Knot | int,
        right: Knot | int = 1,
        scale: Knot | int = 1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(left=left, right=right, scale=scale, _config=_config, **kwargs)

    async def process(
        self,
        left: Annotated[int, Field(description="The left operand.")],
        right: int = 1,
        scale: int = 1,
        **_: Any,
    ) -> int:
        if left < 0:
            raise ValueError("failed: postgres://user:s3cr3t@host/db")
        return (left + right) * scale


class Unnamed(Tool):
    async def process(self, x: str, **_: Any) -> str:
        return x


class TestToolIsAKnotClass(unittest.IsolatedAsyncioTestCase):
    def test_a_tool_is_a_knot_subclass(self) -> None:
        assert issubclass(Tool, Knot)
        assert issubclass(Adder, Knot)

    def test_declaration_derives_from_process_hints(self) -> None:
        declaration = Adder.declaration()
        assert declaration.name == "adder"
        assert declaration.description == "Add two integers."
        assert declaration.parameters == {
            "type": "object",
            "properties": {
                "left": {"type": "integer", "description": "The left operand."},
                "right": {"type": "integer", "default": 1},
                "scale": {"type": "integer", "default": 1},
            },
            "required": ["left"],
        }

    def test_name_defaults_to_snake_case_and_description_to_the_name(self) -> None:
        declaration = Unnamed.declaration()
        assert declaration.name == "unnamed"
        assert declaration.description == "unnamed"

    def test_capability_facets_read_off_the_class(self) -> None:
        assert Adder.requires_approval() is True
        assert Adder.streaming is False
        assert Unnamed.requires_approval() is False
        with self.assertRaisesRegex(TypeError, "not a streaming tool"):
            Unnamed.stream({"x": "1"})

    async def test_base_process_raises_not_implemented(self) -> None:
        with Tapestry():
            bare = Tool(_config=KnotConfig(id="bare"))
        with self.assertRaises(NotImplementedError):
            await bare.process()

    async def test_one_call_is_one_instance_run_by_the_engine(self) -> None:
        with Tapestry() as t:
            Adder(left=2, right=3, _config=KnotConfig(id="call_1"))
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["call_1"] == 5
        row = next(r for r in result.lineage if r.knot_id == "call_1")
        assert row.outcome == "ok"
        assert row.config_values_hash is not None

    async def test_a_failed_call_is_the_engines_err_with_a_scrubbed_record(self) -> None:
        with Tapestry() as t:
            Adder(left=-1, _config=KnotConfig(id="bad"))
        result = await t.run(RunRequest())
        assert not result.succeeded
        record = result.exceptions[0]
        assert record.knot_id == "bad"
        assert record.exc_type == "ValueError"
        assert "s3cr3t" not in record.message
        assert "s3cr3t" not in record.traceback_text
        assert "<redacted>" in record.message

    async def test_bind_hides_the_bound_input_and_fixes_it_for_every_call(self) -> None:
        scaled = Adder.bind(scale=10)
        assert isinstance(scaled, ToolFactory)
        assert "scale" not in scaled.declaration().parameters["properties"]
        outcome = await scaled.run_call(
            ToolCall(tool_name="adder", arguments={"left": 1}, call_id="c")
        )
        assert isinstance(outcome, Ok)
        assert outcome.value == 20

    def test_bind_refuses_a_value_of_the_wrong_type_eagerly(self) -> None:
        with self.assertRaisesRegex(TypeError, "scale"):
            Adder.bind(scale="ten")

    def test_a_bound_input_cannot_be_overridden_by_a_call(self) -> None:
        scaled = Adder.bind(scale=10)
        detail = scaled.validate_arguments({"left": 1, "scale": 2})
        assert detail == {"scale": "unexpected_property"}

    async def test_invoke_shim_warns_and_runs_the_call_outside_the_engine(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = await Adder.invoke({"left": 4, "right": 4})
        assert value == 8
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    async def test_invoke_shim_raises_on_a_failed_call(self) -> None:
        from pirn_agents.exceptions.tool_invocation_error import ToolInvocationError

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaisesRegex(ToolInvocationError, "ValueError"):
                await Adder.invoke({"left": -1})

    def test_clear_credentials_is_noop_by_default(self) -> None:
        with Tapestry():
            call = Adder(left=1, _config=KnotConfig(id="c"))
        call._clear_credentials()  # must not raise


class TestDeprecatedInvokeShapedSubclass(unittest.IsolatedAsyncioTestCase):
    """The pre-ADR shape keeps working as a capability for one cycle."""

    def _legacy_class(self) -> type[Tool]:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")

            class Echo(Tool):
                @property
                def name(self) -> str:
                    return "echo"

                @property
                def description(self) -> str:
                    return "echo the arguments"

                @property
                def parameters_schema(self) -> Mapping[str, Any]:
                    return {"type": "object", "properties": {"a": {"type": "integer"}}}

                async def invoke(self, arguments: Mapping[str, Any]) -> Any:
                    return dict(arguments)

        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
        return Echo

    def test_defining_one_warns_and_marks_it_legacy(self) -> None:
        echo = self._legacy_class()
        assert echo._legacy_tool is True

    async def test_it_becomes_a_capability_through_tool_factory(self) -> None:
        echo = self._legacy_class()()
        factory = ToolFactory.of(echo)
        assert factory.name == "echo"
        assert factory.declaration().parameters == {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
        }
        outcome = await factory.run_call(
            ToolCall(tool_name="echo", arguments={"a": 1}, call_id="c")
        )
        assert isinstance(outcome, Ok)
        assert outcome.value == {"a": 1}

    def test_its_declaration_reads_its_properties(self) -> None:
        echo = self._legacy_class()()
        assert echo.declaration().name == "echo"

    async def test_run_as_a_knot_it_is_refused_with_the_fix_named(self) -> None:
        echo = self._legacy_class()()
        with self.assertRaisesRegex(TypeError, "ToolFactory.of"):
            await echo({})
