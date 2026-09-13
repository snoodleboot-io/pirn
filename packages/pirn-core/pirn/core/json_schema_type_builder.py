"""``JsonSchemaTypeBuilder`` — validators for inputs declared by a JSON schema.

A knot normally gets its input contract from ``process()``'s type hints:
``Knot._build_adapters`` turns each hint into a pydantic ``TypeAdapter``.  A
knot built from a declaration that has no Python signature — an MCP-declared
tool, an OpenAPI operation — has a JSON schema instead.  This builder is the
bridge: it turns each property of an object schema into a Python type that
``TypeAdapter`` validates exactly as it would a hint, so a schema-declared
knot is validated by the same machinery, in the same place, as every other
knot (ADR agents-speaks-core, WS0).

pydantic cannot build a validator from a JSON schema directly, so the builder
maps the schema's vocabulary onto typing constructs (``Literal``, unions,
``list[...]``, ``TypedDict``, ``Annotated[..., Field(...)]``) and lets
pydantic do the rest.

Algorithm:
    ``python_type(fragment)`` for one schema fragment:

    1. ``$ref`` → resolve against the root schema's ``$defs`` /
       ``definitions`` and recurse.
    2. ``const`` → ``Literal[value]``; ``enum`` → ``Literal[values...]``.
    3. ``anyOf`` / ``oneOf`` → union of the members' types.
    4. ``type`` given as a list → union of the listed types; ``"null"``
       anywhere, or OpenAPI ``nullable: true``, adds ``None``.
    5. ``type`` ``string`` / ``integer`` / ``number`` / ``boolean`` /
       ``null`` → ``str`` / ``int`` / ``float`` / ``bool`` / ``None``;
       ``array`` → ``list[items]`` (``list[Any]`` without ``items``);
       ``object`` with ``properties`` → a ``TypedDict`` whose keys are
       ``Required`` per ``required`` (unknown keys kept, or refused when
       ``additionalProperties`` is ``false``); ``object`` without
       ``properties`` → ``dict[str, additionalProperties-or-Any]``.
    6. Numeric, string and array bounds (``minimum``, ``exclusiveMaximum``,
       ``minLength``, ``pattern``, ``maxItems``, ...) become ``Field``
       constraints in an ``Annotated`` wrapper.
    7. Anything else — an empty fragment, an unknown ``type`` — is ``Any``.

    Over the object schema a knot declares, ``input_adapters`` builds one
    ``TypeAdapter`` per property, ``declared`` / ``required`` name the
    property set and its required subset, and ``defaults`` collects the
    properties that carry a ``default``.

References:
    [1] JSON Schema 2020-12, validation vocabulary:
        https://json-schema.org/draft/2020-12/json-schema-validation
    [2] pydantic — ``TypeAdapter`` and ``TypedDict`` validation:
        https://docs.pydantic.dev/latest/concepts/type_adapter/
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar, Literal, NotRequired, Required, Union

from pydantic import ConfigDict, Field, TypeAdapter
from typing_extensions import TypedDict


class JsonSchemaTypeBuilder:
    """Turns JSON-schema fragments into pydantic-validatable Python types."""

    _scalars: ClassVar[dict[str, Any]] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "null": type(None),
    }

    #: JSON-schema keyword -> ``pydantic.Field`` constraint keyword.
    _constraints: ClassVar[dict[str, str]] = {
        "minimum": "ge",
        "maximum": "le",
        "exclusiveMinimum": "gt",
        "exclusiveMaximum": "lt",
        "multipleOf": "multiple_of",
        "minLength": "min_length",
        "maxLength": "max_length",
        "pattern": "pattern",
        "minItems": "min_length",
        "maxItems": "max_length",
    }

    @classmethod
    def validate_input_schema(cls, schema: Any, *, reserved: frozenset[str]) -> dict[str, Any]:
        """Return *schema* as a plain dict if it is a usable input declaration.

        Args:
            schema: The candidate object schema.
            reserved: Property names a knot may not declare (the framework's
                own constructor kwargs).

        Raises:
            TypeError: If *schema* is not an object schema with a
                ``properties`` mapping, or names a reserved property.
        """
        if not isinstance(schema, Mapping):
            raise TypeError(f"input schema must be a mapping, got {type(schema).__name__}")
        declared_type = schema.get("type", "object")
        if declared_type != "object":
            raise TypeError(f"input schema must describe an object, got type={declared_type!r}")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise TypeError("input schema 'properties' must be a mapping")
        clashes = sorted(set(properties) & reserved)
        if clashes:
            raise TypeError(
                f"input schema property name(s) {clashes!r} conflict with framework-reserved kwargs"
            )
        required = schema.get("required", [])
        unknown = sorted(set(required) - set(properties))
        if unknown:
            raise TypeError(f"input schema requires undeclared property name(s) {unknown!r}")
        return {**schema, "properties": dict(properties)}

    @staticmethod
    def declared(schema: Mapping[str, Any]) -> set[str]:
        """The property names the schema declares."""
        return set(schema.get("properties", {}))

    @staticmethod
    def required(schema: Mapping[str, Any]) -> set[str]:
        """The property names the schema requires."""
        return set(schema.get("required", []))

    @staticmethod
    def defaults(schema: Mapping[str, Any]) -> dict[str, Any]:
        """Property name -> declared default, for the properties that have one."""
        return {
            name: fragment["default"]
            for name, fragment in schema.get("properties", {}).items()
            if isinstance(fragment, Mapping) and "default" in fragment
        }

    @classmethod
    def input_adapters(cls, schema: Mapping[str, Any]) -> dict[str, TypeAdapter[Any]]:
        """One ``TypeAdapter`` per declared property, in declaration order."""
        return {
            name: TypeAdapter(cls.python_type(fragment, root=schema))
            for name, fragment in schema.get("properties", {}).items()
        }

    @classmethod
    def python_type(cls, fragment: Any, *, root: Mapping[str, Any] | None = None) -> Any:
        """Return the Python type that validates values of *fragment*.

        Args:
            fragment: A JSON-schema fragment (``True``/``{}`` accept anything).
            root: The schema ``$ref`` pointers resolve against; defaults to
                *fragment* itself.
        """
        if not isinstance(fragment, Mapping):
            return Any
        root = root if root is not None else fragment
        base = cls._unconstrained_type(fragment, root)
        constraints = {
            keyword: fragment[key] for key, keyword in cls._constraints.items() if key in fragment
        }
        if not constraints or base is Any:
            return base
        return Annotated[base, Field(**constraints)]

    @classmethod
    def _unconstrained_type(cls, fragment: Mapping[str, Any], root: Mapping[str, Any]) -> Any:
        if "$ref" in fragment:
            return cls.python_type(cls._resolve_ref(fragment["$ref"], root), root=root)
        if "const" in fragment:
            return Literal[fragment["const"]]
        if "enum" in fragment:
            values = tuple(fragment["enum"])
            return Literal[values] if values else Any  # type: ignore[valid-type]
        for combinator in ("anyOf", "oneOf"):
            if combinator in fragment:
                members = [cls.python_type(member, root=root) for member in fragment[combinator]]
                return cls._union(members)
        declared = fragment.get("type")
        nullable = bool(fragment.get("nullable", False))
        if isinstance(declared, list):
            members = [cls._typed(fragment, name, root) for name in declared]
            return cls._union(members)
        if declared is None:
            # No ``type``: an object shape may still be implied by ``properties``.
            if "properties" in fragment:
                return cls._typed(fragment, "object", root)
            return Any
        resolved = cls._typed(fragment, declared, root)
        if nullable and resolved is not Any:
            return cls._union([resolved, type(None)])
        return resolved

    @classmethod
    def _typed(cls, fragment: Mapping[str, Any], name: str, root: Mapping[str, Any]) -> Any:
        if name in cls._scalars:
            return cls._scalars[name]
        if name == "array":
            items = fragment.get("items")
            return list[cls.python_type(items, root=root)] if items is not None else list[Any]  # type: ignore[misc]
        if name == "object":
            return cls._object_type(fragment, root)
        return Any

    @classmethod
    def _object_type(cls, fragment: Mapping[str, Any], root: Mapping[str, Any]) -> Any:
        properties = fragment.get("properties")
        additional = fragment.get("additionalProperties", True)
        if not isinstance(properties, Mapping) or not properties:
            value_type = cls.python_type(additional, root=root) if additional is not False else Any
            return dict[str, value_type]  # type: ignore[valid-type]
        required = set(fragment.get("required", []))
        fields: dict[str, Any] = {}
        for prop_name, prop_fragment in properties.items():
            prop_type = cls.python_type(prop_fragment, root=root)
            fields[prop_name] = (
                Required[prop_type] if prop_name in required else NotRequired[prop_type]  # type: ignore[valid-type]
            )
        typed = TypedDict(str(fragment.get("title", "Object")), fields)  # type: ignore[misc]
        typed.__pydantic_config__ = ConfigDict(  # type: ignore[attr-defined]
            extra="forbid" if additional is False else "allow"
        )
        return typed

    @staticmethod
    def _union(members: list[Any]) -> Any:
        unique: list[Any] = []
        for member in members:
            if member not in unique:
                unique.append(member)
        if not unique:
            return Any
        if len(unique) == 1:
            return unique[0]
        return Union[tuple(unique)]  # noqa: UP007 -- built dynamically from a runtime list

    @staticmethod
    def _resolve_ref(ref: str, root: Mapping[str, Any]) -> Any:
        for prefix in ("#/$defs/", "#/definitions/"):
            if ref.startswith(prefix):
                store = root.get(prefix[2:-1], {})
                name = ref[len(prefix) :]
                if name not in store:
                    raise TypeError(f"input schema $ref {ref!r} is not defined")
                return store[name]
        raise TypeError(f"input schema $ref {ref!r} is not a local reference")
