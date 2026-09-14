"""``StructuredContentValidator`` — parse-and-validate native JSON content.

A small collaborator shared by the content-returning native paths
(:class:`pirn_agents.specializations.structured_output.native_schema_strategy.NativeSchemaStrategy`
and
:class:`pirn_agents.specializations.structured_output.constrained_decoding_strategy.ConstrainedDecodingStrategy`).
It decodes a provider's raw structured content string as JSON and validates it
against the bound :class:`pydantic.BaseModel`, raising
:class:`StructuredDecodeError` on either failure so the decoder can fall back.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from pirn_agents.specializations.structured_output.structured_decode_error import (
    StructuredDecodeError,
)


class StructuredContentValidator:
    """Decode native content as JSON and validate it against a model."""

    def __init__(self, *, model_class: type[BaseModel]) -> None:
        """Bind the validator to a target model.

        Args:
            model_class: The :class:`pydantic.BaseModel` subclass to validate
                decoded content against.

        Raises:
            TypeError: If ``model_class`` is not a ``BaseModel`` subclass.
        """
        if not isinstance(model_class, type) or not issubclass(model_class, BaseModel):
            raise TypeError(
                "StructuredContentValidator: model_class must be a BaseModel "
                f"subclass, got {model_class!r}"
            )
        self._model_class = model_class

    def validate(self, content: str) -> BaseModel:
        """Return a validated model instance parsed from ``content``.

        Args:
            content: The raw structured-output content string returned by a
                provider.

        Returns:
            A validated instance of the bound model class.

        Raises:
            StructuredDecodeError: If ``content`` is not valid JSON or fails
                model validation.
        """
        try:
            data: Any = json.loads(content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise StructuredDecodeError(
                f"StructuredContentValidator: native content was not valid JSON: {exc}"
            ) from exc
        try:
            return self._model_class.model_validate(data)
        except ValidationError as exc:
            raise StructuredDecodeError(
                f"StructuredContentValidator: native content failed model validation: {exc}"
            ) from exc
