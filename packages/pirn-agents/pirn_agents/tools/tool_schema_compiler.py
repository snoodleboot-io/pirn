"""``ToolSchemaCompiler`` — deprecated (one cycle); core renders tool schemas now.

Before the ADR "agents speaks core" (WS1) this class re-implemented the
annotation→JSON-Schema mapping core already performs when it builds a knot's
``TypeAdapter``\\s.  A tool's declaration is now ``Knot.input_json_schema()``
(the same hints ``validate_io`` checks, rendered by pydantic), and a model
declared schema goes through ``Knot._input_schema_override`` /
``JsonSchemaTypeBuilder``.  Every method here forwards to that machinery and
warns; the class will be removed next cycle.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping
from typing import Any

from pirn_agents.tools.tool_decorator import ToolDecorator


class ToolSchemaCompiler:
    """Deprecated shim over core's schema rendering."""

    def __init__(self) -> None:
        warnings.warn(
            "ToolSchemaCompiler is deprecated (ADR agents-speaks-core WS1): a tool's schema is "
            "Knot.input_json_schema(); use Tool.declaration() / ToolFactory.declaration()",
            DeprecationWarning,
            stacklevel=2,
        )

    def annotation_to_schema(self, annotation: Any) -> dict[str, Any]:
        """Render one annotation the way core's ``TypeAdapter.json_schema`` does."""
        import inspect

        from pydantic import PydanticSchemaGenerationError, TypeAdapter

        if annotation is inspect.Parameter.empty or annotation is Any:
            return {}
        try:
            fragment = dict(TypeAdapter(annotation).json_schema())
        except PydanticSchemaGenerationError:
            return {}
        fragment.pop("title", None)
        return fragment

    def is_arg_model(self, spec: Any) -> bool:
        """Return whether ``spec`` is a usable pydantic model or dataclass type."""
        return ToolDecorator._is_arg_model(spec)

    def model_json_schema(self, model: type) -> dict[str, Any]:
        """Return the JSON schema for a pydantic model or dataclass ``model``."""
        return ToolDecorator._model_json_schema(model)

    def model_validator(self, model: type) -> Callable[[Mapping[str, Any]], Any]:
        """Return a callable that validates/coerces a mapping into ``model``."""
        return ToolDecorator._model_validator(model)

    def schema_from_signature(
        self,
        fn: Callable[..., Any],
        *,
        arg_docs: Mapping[str, str] | None,
        examples: Mapping[str, Any] | None,
        exclude: frozenset[str],
    ) -> dict[str, Any]:
        """Derive a declaration ``parameters`` object from a function's signature.

        Forwards to ``@tool``: the generated knot class's ``input_json_schema()``
        with ``arg_docs``/``examples`` applied; ``exclude`` names are dropped.
        """
        from pirn_agents.tools.tool_permissions import ToolPermissions

        factory = ToolDecorator.build(
            fn,
            name=None,
            description=None,
            args_model=None,
            arg_docs=arg_docs,
            examples=examples,
            permissions=ToolPermissions(),
            state=None,
        )
        schema = dict(factory.declaration().parameters)
        properties = {k: v for k, v in schema.get("properties", {}).items() if k not in exclude}
        required = [k for k in schema.get("required", []) if k not in exclude]
        out: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            out["required"] = required
        return out

    def return_schema(self, fn: Callable[..., Any]) -> dict[str, Any] | None:
        """Derive a JSON Schema fragment from a function's return annotation."""
        return ToolDecorator._return_schema(fn)
