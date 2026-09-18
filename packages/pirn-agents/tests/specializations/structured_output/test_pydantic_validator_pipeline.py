"""Tests for :class:`PydanticValidatorPipeline`."""

from __future__ import annotations

import unittest
from collections.abc import Callable

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pydantic import BaseModel, ConfigDict
from pydantic.errors import PydanticInvalidForJsonSchema

from pirn_agents.specializations.structured_output.pydantic_validator_pipeline import (
    PydanticValidatorPipeline,
)
from tests.specializations.conftest import (
    StubLLMProvider,
)


class _UserRecord(BaseModel):
    name: str
    age: int


class TestPydanticValidatorPipelineValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_basemodel_class(self) -> None:
        llm = StubLLMProvider(['{"name": "x", "age": 1}'])
        knot = PydanticValidatorPipeline.__new__(PydanticValidatorPipeline)
        with self.assertRaisesRegex(TypeError, "model_class must be a BaseModel"):
            await knot.process(
                prompt="extract",
                llm=llm,
                model_class=int,  # type: ignore[arg-type]
                max_retries=3,
            )

    async def test_rejects_zero_max_retries(self) -> None:
        llm = StubLLMProvider(['{"name": "x", "age": 1}'])
        knot = PydanticValidatorPipeline.__new__(PydanticValidatorPipeline)
        with self.assertRaisesRegex(ValueError, "max_retries"):
            await knot.process(
                prompt="extract",
                llm=llm,
                model_class=_UserRecord,
                max_retries=0,
            )


class TestPydanticValidatorPipelineRejectsUnschematisableModels(unittest.IsolatedAsyncioTestCase):
    """A model with no JSON schema fails loudly instead of prompting for nothing.

    Before PIR-873 ``_derive_schema`` caught every exception and returned an
    empty mapping, so the extraction prompt named no fields at all and the run
    then blamed the model for a reply that could never have validated.
    """

    async def test_model_without_a_json_schema_raises(self) -> None:
        class _Unschematisable(BaseModel):
            model_config = ConfigDict(arbitrary_types_allowed=True)

            handler: Callable[[int], int]

        llm = StubLLMProvider(['{"handler": 1}'])
        knot = PydanticValidatorPipeline.__new__(PydanticValidatorPipeline)
        with self.assertRaisesRegex(TypeError, "has no JSON schema"):
            await knot.process(
                prompt="extract",
                llm=llm,
                model_class=_Unschematisable,
                max_retries=3,
            )

    async def test_the_pydantic_cause_is_chained(self) -> None:
        class _AlsoUnschematisable(BaseModel):
            model_config = ConfigDict(arbitrary_types_allowed=True)

            handler: Callable[[int], int]

        llm = StubLLMProvider(['{"handler": 1}'])
        knot = PydanticValidatorPipeline.__new__(PydanticValidatorPipeline)
        with self.assertRaises(TypeError) as caught:
            await knot.process(
                prompt="extract",
                llm=llm,
                model_class=_AlsoUnschematisable,
                max_retries=3,
            )
        assert isinstance(caught.exception.__cause__, PydanticInvalidForJsonSchema)


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
