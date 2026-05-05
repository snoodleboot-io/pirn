"""Tests for :class:`PydanticValidatorPipeline`."""

from __future__ import annotations
import unittest

from pydantic import BaseModel

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.pydantic_validator_pipeline import (  # noqa: E501
    PydanticValidatorPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
)


class _UserRecord(BaseModel):
    name: str
    age: int


class TestPydanticValidatorPipelineConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_basemodel_class(self) -> None:
        llm = StubLLMProvider(['{"name": "x", "age": 1}'])
        with self.assertRaisesRegex(TypeError, "model_class must be a BaseModel"):
            with Tapestry():
                PydanticValidatorPipeline(
                    prompt="extract",
                    llm=llm,
                    model_class=int,  # type: ignore[arg-type]
                    _config=KnotConfig(id="validate"),
                )

    async def test_rejects_zero_max_retries(self) -> None:
        llm = StubLLMProvider(['{"name": "x", "age": 1}'])
        with self.assertRaisesRegex(ValueError, "max_retries"):
            with Tapestry():
                PydanticValidatorPipeline(
                    prompt="extract",
                    llm=llm,
                    model_class=_UserRecord,
                    max_retries=0,
                    _config=KnotConfig(id="validate"),
                )


class TestPydanticValidatorPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_validated_model_instance(self) -> None:
        llm = StubLLMProvider(['{"name": "Ada", "age": 36}'])
        with Tapestry() as t:
            PydanticValidatorPipeline(
                prompt="extract a user",
                llm=llm,
                model_class=_UserRecord,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        instance = result.outputs["validate"]
        assert isinstance(instance, _UserRecord)
        assert instance.name == "Ada"
        assert instance.age == 36

    async def test_retries_on_validation_error(self) -> None:
        # First attempt returns wrong type for ``age`` (string instead of int);
        # the validator surfaces the pydantic error to the next prompt.
        llm = StubLLMProvider(
            [
                '{"name": "Ada", "age": "thirty-six"}',
                '{"name": "Ada", "age": 36}',
            ]
        )
        with Tapestry() as t:
            PydanticValidatorPipeline(
                prompt="extract a user",
                llm=llm,
                model_class=_UserRecord,
                max_retries=3,
                _config=KnotConfig(id="validate"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        instance = result.outputs["validate"]
        assert isinstance(instance, _UserRecord)
        assert instance.age == 36
        assert len(llm.calls) == 2
