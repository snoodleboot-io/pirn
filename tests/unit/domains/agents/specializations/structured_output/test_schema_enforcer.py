"""Unit tests for :class:`SchemaEnforcer`."""

from __future__ import annotations

from typing import Any
import unittest

from pydantic import BaseModel

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.schema_enforcer import (
    SchemaEnforcer,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class _PersonModel(BaseModel):
    name: str
    age: int


class TestSchemaEnforcerConstruction(unittest.TestCase):
    def test_rejects_non_base_model_class(self) -> None:
        with self.assertRaisesRegex(TypeError, "BaseModel"):
            with Tapestry():
                SchemaEnforcer(
                    response=AgentResponse(content="{}", finish_reason="stop"),
                    model_class=str,  # type: ignore[arg-type]
                    _config=KnotConfig(id="se"),
                )


class TestSchemaEnforcerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_validates_valid_json_against_model(self) -> None:
        response = AgentResponse(
            content='{"name": "Alice", "age": 30}',
            finish_reason="stop",
        )
        with Tapestry() as t:
            SchemaEnforcer(
                response=response,
                model_class=_PersonModel,
                _config=KnotConfig(id="se"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["se"]
        assert isinstance(out, _PersonModel)
        assert out.name == "Alice"
        assert out.age == 30

    async def test_raises_on_invalid_json(self) -> None:
        response = AgentResponse(content="not json", finish_reason="stop")
        with Tapestry() as t:
            SchemaEnforcer(
                response=response,
                model_class=_PersonModel,
                _config=KnotConfig(id="se"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_raises_on_schema_mismatch(self) -> None:
        response = AgentResponse(
            content='{"name": "Bob", "age": "not-an-int"}',
            finish_reason="stop",
        )
        with Tapestry() as t:
            SchemaEnforcer(
                response=response,
                model_class=_PersonModel,
                _config=KnotConfig(id="se"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_non_agent_response(self) -> None:
        with Tapestry():
            with self.assertRaises(TypeError):
                SchemaEnforcer(
                    response="not-a-response",  # type: ignore[arg-type]
                    model_class=_PersonModel,
                    _config=KnotConfig(id="se"),
                )
