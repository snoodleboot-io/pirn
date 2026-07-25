"""``ConstrainedDecodingMapper`` — schema → grammar/regex-constrained request.

The S3 building block for local providers (vLLM/Ollama style) that expose
grammar/regex-constrained decoding. It generates a constraint from the target
schema — always a JSON-schema constraint, plus a regex alternation when the
schema is a simple string enum — and asks the provider to pass it through its
native decode options. Providers that do not advertise constrained decoding are
skipped cleanly by returning ``None`` (no error).

Constraint *generation* is pure and backend-free. Optionally *compiling* the
grammar against a real engine is delegated to the lazily-imported
:mod:`pirn_agents.specializations.structured_output._grammar_backend`, keeping
the core import backend-free.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from pirn_agents.specializations.structured_output import _grammar_backend
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)


class ConstrainedDecodingMapper:
    """Generate a grammar/regex constraint and map it to a provider request."""

    def __init__(
        self,
        *,
        schema: type[BaseModel] | Mapping[str, Any],
        validate_grammar: bool = False,
    ) -> None:
        """Bind the mapper to a target schema and grammar-validation policy.

        Args:
            schema: A :class:`pydantic.BaseModel` subclass, or a raw JSON Schema
                mapping, to constrain generation against.
            validate_grammar: When ``True``, the generated constraint is
                compiled through the optional grammar backend before mapping
                (requires the ``grammar`` extra).

        Raises:
            TypeError: If ``schema`` is neither a ``BaseModel`` subclass nor a
                mapping.
        """
        if not self._is_model_class(schema) and not isinstance(schema, Mapping):
            raise TypeError(
                "ConstrainedDecodingMapper: schema must be a BaseModel subclass "
                f"or a JSON-Schema mapping, got {type(schema).__name__}"
            )
        self._schema: type[BaseModel] | Mapping[str, Any] = schema
        self._validate_grammar = bool(validate_grammar)

    def constraint(self) -> Mapping[str, Any]:
        """Return the generated grammar/regex constraint for the schema."""
        schema = self.json_schema()
        constraint: dict[str, Any] = {"json_schema": dict(schema)}
        regex = self._enum_regex(schema)
        if regex is not None:
            constraint["regex"] = regex
        return constraint

    def map_request(self, provider: StructuredOutputProvider) -> Mapping[str, Any] | None:
        """Return native decode options, or ``None`` when unsupported.

        Args:
            provider: A capability-advertising :class:`StructuredOutputProvider`.

        Returns:
            The provider's native constrained-decoding request options when it
            advertises support, otherwise ``None`` (clean, error-free skip).

        Raises:
            TypeError: If ``provider`` is not a :class:`StructuredOutputProvider`.
            ImportError: If ``validate_grammar`` is set and the ``grammar``
                backend is not installed.
        """
        if not isinstance(provider, StructuredOutputProvider):
            raise TypeError(
                "ConstrainedDecodingMapper: provider must be a "
                f"StructuredOutputProvider, got {type(provider).__name__}"
            )
        if not provider.structured_output_capability().constrained_decoding:
            return None
        constraint = self.constraint()
        if self._validate_grammar:
            _grammar_backend.compile_constraint(constraint)
        return provider.constrained_decoding_option(constraint)

    def json_schema(self) -> Mapping[str, Any]:
        """Return the target's JSON Schema (derived from the model if needed)."""
        if self._is_model_class(self._schema):
            model_class: type[BaseModel] = self._schema  # type: ignore[assignment]
            return model_class.model_json_schema()
        return self._schema  # type: ignore[return-value]

    @staticmethod
    def _enum_regex(schema: Mapping[str, Any]) -> str | None:
        enum = schema.get("enum")
        if isinstance(enum, list) and enum and all(isinstance(value, str) for value in enum):
            import re

            alternation = "|".join(re.escape(str(value)) for value in enum)
            return f"^({alternation})$"
        return None

    @staticmethod
    def _is_model_class(schema: Any) -> bool:
        return isinstance(schema, type) and issubclass(schema, BaseModel)
