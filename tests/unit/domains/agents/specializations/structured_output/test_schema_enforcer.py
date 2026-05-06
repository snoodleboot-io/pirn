"""Unit tests for :class:`SchemaEnforcer`."""

from __future__ import annotations

from typing import Any
import unittest

from pydantic import BaseModel, ValidationError

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.structured_output.schema_enforcer import (
    SchemaEnforcer,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class _PersonModel(BaseModel):
    name: str
    age: int


def _make_knot() -> SchemaEnforcer:
    with Tapestry():
        return SchemaEnforcer(
            response=AgentResponse(content="{}", finish_reason="stop"),
            model_class=_PersonModel,
            _config=KnotConfig(id="se"),
        )


class TestSchemaEnforcerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_base_model_class(self) -> None:
        knot = _make_knot()
        response = AgentResponse(content="{}", finish_reason="stop")
        with self.assertRaisesRegex(TypeError, "BaseModel"):
            await knot.process(response=response, model_class=str)  # type: ignore[arg-type]

    async def test_rejects_non_agent_response(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(
                response="not-a-response",  # type: ignore[arg-type]
                model_class=_PersonModel,
            )

    async def test_validates_valid_json_against_model(self) -> None:
        knot = _make_knot()
        response = AgentResponse(
            content='{"name": "Alice", "age": 30}',
            finish_reason="stop",
        )
        result = await knot.process(response=response, model_class=_PersonModel)
        assert isinstance(result, _PersonModel)
        assert result.name == "Alice"
        assert result.age == 30

    async def test_raises_on_invalid_json(self) -> None:
        knot = _make_knot()
        response = AgentResponse(content="not json", finish_reason="stop")
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            await knot.process(response=response, model_class=_PersonModel)

    async def test_raises_on_schema_mismatch(self) -> None:
        knot = _make_knot()
        response = AgentResponse(
            content='{"name": "Bob", "age": "not-an-int"}',
            finish_reason="stop",
        )
        with self.assertRaises(ValidationError):
            await knot.process(response=response, model_class=_PersonModel)
