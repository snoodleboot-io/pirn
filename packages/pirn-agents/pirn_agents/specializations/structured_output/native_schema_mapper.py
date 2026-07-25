"""``NativeSchemaMapper`` — target schema → native structured-output request.

The S1 building block. Given a target pydantic model *or* a raw JSON Schema, it
consults a provider's advertised :class:`StructuredOutputCapability` and, when
native schema decoding is supported, asks the provider to shape the target into
its native structured-output request options (an OpenAI-style
``response_format`` fragment, a Messages-style equivalent, …). When the
provider does not advertise native schema support the mapper reports
"unsupported" by returning ``None`` so callers can fall back.

The mapper is provider-neutral: it never emits a vendor-specific shape itself —
that shaping lives behind the provider's ``native_schema_option`` boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)


class NativeSchemaMapper:
    """Map a pydantic/JSON-Schema target onto a provider's native request."""

    def __init__(
        self,
        *,
        schema: type[BaseModel] | Mapping[str, Any],
        name: str | None = None,
    ) -> None:
        """Bind the mapper to a target schema and an optional schema name.

        Args:
            schema: A :class:`pydantic.BaseModel` subclass, or a raw JSON Schema
                mapping, describing the desired output structure.
            name: Optional name advertised alongside the schema; defaults to the
                model class name, or ``"structured_output"`` for a raw schema.

        Raises:
            TypeError: If ``schema`` is neither a ``BaseModel`` subclass nor a
                mapping, or ``name`` is neither a string nor ``None``.
        """
        if not self._is_model_class(schema) and not isinstance(schema, Mapping):
            raise TypeError(
                "NativeSchemaMapper: schema must be a BaseModel subclass or a "
                f"JSON-Schema mapping, got {type(schema).__name__}"
            )
        if name is not None and not isinstance(name, str):
            raise TypeError(
                f"NativeSchemaMapper: name must be a str or None, got {type(name).__name__}"
            )
        self._schema: type[BaseModel] | Mapping[str, Any] = schema
        self._name: str = name if name is not None else self._default_name(schema)

    def map_request(self, provider: StructuredOutputProvider) -> Mapping[str, Any] | None:
        """Return native request options, or ``None`` when unsupported.

        Args:
            provider: A capability-advertising :class:`StructuredOutputProvider`.

        Returns:
            The provider's native structured-output request options when it
            advertises native schema support, otherwise ``None`` (the
            "unsupported" signal telling callers to fall back).

        Raises:
            TypeError: If ``provider`` is not a :class:`StructuredOutputProvider`.
        """
        if not isinstance(provider, StructuredOutputProvider):
            raise TypeError(
                "NativeSchemaMapper: provider must be a StructuredOutputProvider, "
                f"got {type(provider).__name__}"
            )
        if not provider.structured_output_capability().native_schema:
            return None
        return provider.native_schema_option(self.json_schema(), name=self._name)

    def json_schema(self) -> Mapping[str, Any]:
        """Return the target's JSON Schema (derived from the model if needed)."""
        if self._is_model_class(self._schema):
            model_class: type[BaseModel] = self._schema  # type: ignore[assignment]
            return model_class.model_json_schema()
        return self._schema  # type: ignore[return-value]

    @staticmethod
    def _is_model_class(schema: Any) -> bool:
        return isinstance(schema, type) and issubclass(schema, BaseModel)

    @staticmethod
    def _default_name(schema: type[BaseModel] | Mapping[str, Any]) -> str:
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.__name__
        return "structured_output"
