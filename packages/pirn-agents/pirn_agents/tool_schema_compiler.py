"""``ToolSchemaCompiler`` — derive JSON-Schema from Python type hints / models.

The single home for the annotation→JSON-Schema mapping used both by the
``@tool`` decorator (for a plain function's signature) and by
:func:`~pirn_agents.agent_schema.derive_agent_schema` (for a ``SubTapestry``
agent's ``process`` signature). Grouping the mapping, the signature/return
derivation, and the pydantic-model bridging into one collaborator keeps the
Python-type → schema logic in one place instead of scattered free functions, and
holds the primitive-type table as instance state rather than a module constant.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import is_dataclass
from functools import partial
from typing import Any, Union, get_type_hints

from pydantic import BaseModel, TypeAdapter


class ToolSchemaCompiler:
    """Compile JSON-Schema fragments from annotations, signatures, and models."""

    def __init__(self) -> None:
        """Hold the primitive Python-type → JSON-Schema-type table."""
        self._py_to_json_type: dict[Any, str] = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            bytes: "string",
            list: "array",
            dict: "object",
        }

    def annotation_to_schema(self, annotation: Any) -> dict[str, Any]:
        """Best-effort conversion of a Python type hint to a JSON Schema fragment."""
        if annotation is inspect.Parameter.empty or annotation is Any:
            return {}

        origin = getattr(annotation, "__origin__", None)
        args: tuple[Any, ...] = getattr(annotation, "__args__", ()) or ()

        # Optional[T] / Union[T, None]
        if origin is Union:
            non_none = [a for a in args if a is not type(None)]
            nullable = len(non_none) < len(args)
            if len(non_none) == 1:
                inner = self.annotation_to_schema(non_none[0])
                if nullable:
                    t = inner.get("type")
                    if isinstance(t, str):
                        inner = {**inner, "type": [t, "null"]}
                return inner
            return {}

        # Python 3.10+ `X | Y` syntax surfaces as types.UnionType
        try:
            import types as _types

            if isinstance(annotation, _types.UnionType):
                parts = list(args) if args else []
                # Fall back to __args__ populated by __class_getitem__
                if not parts:
                    parts = list(getattr(annotation, "__args__", []))
                non_none = [a for a in parts if a is not type(None)]
                nullable = len(non_none) < len(parts)
                if len(non_none) == 1:
                    inner = self.annotation_to_schema(non_none[0])
                    if nullable:
                        t = inner.get("type")
                        if isinstance(t, str):
                            inner = {**inner, "type": [t, "null"]}
                    return inner
                return {}
        except AttributeError:
            pass

        # list[T] / List[T]
        if origin is list:
            schema: dict[str, Any] = {"type": "array"}
            if args:
                schema["items"] = self.annotation_to_schema(args[0])
            return schema

        # dict[K, V] / Dict[K, V]
        if origin is dict:
            return {"type": "object"}

        json_type = self._py_to_json_type.get(annotation)
        if json_type:
            return {"type": json_type}

        # Unknown annotation — leave the field schema-less so tools still work.
        return {}

    def is_arg_model(self, spec: Any) -> bool:
        """Return whether ``spec`` is a usable pydantic model or dataclass type."""
        if isinstance(spec, type) and issubclass(spec, BaseModel):
            return True
        return isinstance(spec, type) and is_dataclass(spec)

    def model_json_schema(self, model: type) -> dict[str, Any]:
        """Return the JSON schema for a pydantic model or dataclass ``model``."""
        if issubclass(model, BaseModel):
            schema = dict(model.model_json_schema())
        else:  # stdlib dataclass, validated via a pydantic TypeAdapter
            schema = dict(TypeAdapter(model).json_schema())
        schema.pop("title", None)
        return schema

    def model_validator(self, model: type) -> Callable[[Mapping[str, Any]], Any]:
        """Return a callable that validates/coerces a mapping into ``model``."""
        if issubclass(model, BaseModel):
            return partial(self._validate_with_model, model)
        return partial(self._validate_with_adapter, TypeAdapter(model))

    def schema_from_signature(
        self,
        fn: Callable[..., Any],
        *,
        arg_docs: Mapping[str, str] | None,
        examples: Mapping[str, Any] | None,
        exclude: frozenset[str],
    ) -> dict[str, Any]:
        """Derive a JSON Schema ``parameters`` object from a function's signature.

        ``arg_docs`` and ``examples`` decorate the per-argument fragments with
        ``description``/``examples`` keys; ``exclude`` drops reserved parameters
        (e.g. an injected ``state``) from the surfaced schema.
        """
        sig = inspect.signature(fn)
        try:
            hints = get_type_hints(fn)
        except Exception:
            hints = {}

        properties: dict[str, dict[str, Any]] = {}
        required: list[str] = []

        for name, param in sig.parameters.items():
            if name in ("self", "cls") or name in exclude:
                continue
            annotation = hints.get(name, inspect.Parameter.empty)
            prop = self.annotation_to_schema(annotation)
            if arg_docs and name in arg_docs:
                prop["description"] = arg_docs[name]
            if examples and name in examples:
                prop["examples"] = [examples[name]]
            properties[name] = prop
            if param.default is inspect.Parameter.empty:
                required.append(name)

        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    def return_schema(self, fn: Callable[..., Any]) -> dict[str, Any] | None:
        """Derive a JSON Schema fragment from a function's return annotation."""
        try:
            hints = get_type_hints(fn)
        except Exception:
            return None
        annotation = hints.get("return", inspect.Parameter.empty)
        if annotation is inspect.Parameter.empty or annotation is None or annotation is type(None):
            return None
        if self.is_arg_model(annotation):
            return self.model_json_schema(annotation)
        fragment = self.annotation_to_schema(annotation)
        return fragment or None

    @staticmethod
    def _validate_with_model(model: type[BaseModel], data: Mapping[str, Any]) -> Any:
        """Validate ``data`` into a pydantic ``model`` instance."""
        return model.model_validate(dict(data))

    @staticmethod
    def _validate_with_adapter(adapter: TypeAdapter[Any], data: Mapping[str, Any]) -> Any:
        """Validate ``data`` into a dataclass via a pydantic ``adapter``."""
        return adapter.validate_python(dict(data))
