"""Unit tests for :class:`Tool` — a capability expressed as a ``Knot`` class (ADR WS1)."""

from __future__ import annotations

import unittest
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

    def test_clear_credentials_is_noop_by_default(self) -> None:
        with Tapestry():
            call = Adder(left=1, _config=KnotConfig(id="c"))
        call._clear_credentials()  # must not raise


class TestArgumentValidationIsolatesBrokenSchemaFragments(unittest.TestCase):
    """One unbuildable property must not disable validation of the others (PIR-873).

    ``validate_arguments`` used to build every property's validator in one
    call and fall back to ``{}`` on any error, so a single malformed fragment
    silently switched off argument type-checking for the whole tool.
    """

    @staticmethod
    def _factory() -> ToolFactory:
        """A declaration whose ``right`` fragment has a mistyped ``minLength``."""
        return ToolFactory(
            Adder,
            parameters={
                "type": "object",
                "properties": {
                    "left": {"type": "integer"},
                    "right": {"type": "string", "minLength": "nope"},
                },
                "required": ["left"],
            },
        )

    def test_a_mistyped_argument_is_still_refused_next_to_a_broken_fragment(self) -> None:
        detail = self._factory().validate_arguments({"left": "twelve"})
        assert detail == {"left": "expected:integer,got:str"}

    def test_an_argument_whose_own_fragment_cannot_be_validated_is_refused(self) -> None:
        detail = self._factory().validate_arguments({"left": 1, "right": "x"})
        assert detail == {"right": "unvalidatable_schema:TypeError"}

    def test_a_broken_fragment_nobody_supplied_a_value_for_is_not_an_error(self) -> None:
        assert self._factory().validate_arguments({"left": 1}) == {}
