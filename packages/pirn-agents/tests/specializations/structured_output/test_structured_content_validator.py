"""Unit tests for :class:`StructuredContentValidator`."""

from __future__ import annotations

import unittest

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.structured_content_validator import (
    StructuredContentValidator,
)
from pirn_agents.specializations.structured_output.structured_decode_error import (
    StructuredDecodeError,
)


class _UserRecord(BaseModel):
    name: str
    age: int


class TestStructuredContentValidator(unittest.TestCase):
    def test_validates_valid_json(self) -> None:
        validator = StructuredContentValidator(model_class=_UserRecord)

        instance = validator.validate('{"name": "Ada", "age": 36}')

        assert isinstance(instance, _UserRecord)
        assert instance.name == "Ada"
        assert instance.age == 36

    def test_rejects_non_json_content(self) -> None:
        validator = StructuredContentValidator(model_class=_UserRecord)

        with self.assertRaisesRegex(StructuredDecodeError, "not valid JSON"):
            validator.validate("not json at all")

    def test_rejects_content_failing_model_validation(self) -> None:
        validator = StructuredContentValidator(model_class=_UserRecord)

        with self.assertRaisesRegex(StructuredDecodeError, "failed model validation"):
            validator.validate('{"name": "Ada"}')

    def test_rejects_non_basemodel_model_class(self) -> None:
        with self.assertRaisesRegex(TypeError, "model_class must be a BaseModel"):
            StructuredContentValidator(model_class=int)  # type: ignore[type-var]


if __name__ == "__main__":
    unittest.main()
