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

import functools
import types
from collections.abc import Mapping
from typing import Annotated, Any, ClassVar, Literal, NotRequired, Required, Union

from pydantic import ConfigDict, Field, TypeAdapter
from typing_extensions import TypedDict

from pirn.core.json_schema_field_constraints import JsonSchemaFieldConstraints
from pirn.core.shape_guard import ShapeGuard


class JsonSchemaTypeBuilder:
    """Turns JSON-schema fragments into pydantic-validatable Python types."""

    _scalars: ClassVar[dict[str, Any]] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "null": type(None),
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
        if not ShapeGuard.is_str_keyed_mapping(schema):
            raise TypeError(f"input schema must be a mapping, got {type(schema).__name__}")
        declared_type = schema.get("type", "object")
        if declared_type != "object":
            raise TypeError(f"input schema must describe an object, got type={declared_type!r}")
        properties = schema.get("properties", {})
        if not ShapeGuard.is_str_keyed_mapping(properties):
            raise TypeError("input schema 'properties' must be a mapping")
        clashes = sorted(set(properties) & reserved)
        if clashes:
            raise TypeError(
                f"input schema property name(s) {clashes!r} conflict with framework-reserved kwargs"
            )
        required = schema.get("required", [])
        if not ShapeGuard.is_list_or_tuple(required):
            raise TypeError("input schema 'required' must be a list of property names")
        unknown = sorted(str(name) for name in set(required) - set(properties))
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
        if not ShapeGuard.is_str_keyed_mapping(fragment):
            return Any
        schema_root: Mapping[str, Any] = root if root is not None else fragment
        base = cls._unconstrained_type(fragment, schema_root)
        constraints = cls._field_constraints(fragment)
        if not constraints or base is Any:
            return base
        return Annotated[base, Field(**constraints)]

    @classmethod
    def _field_constraints(cls, fragment: Mapping[str, object]) -> JsonSchemaFieldConstraints:
        """Map the fragment's bound keywords onto ``pydantic.Field`` constraints.

        Raises:
            TypeError: If a bound keyword carries a value of the wrong JSON type.
        """
        constraints: JsonSchemaFieldConstraints = {}
        minimum = cls._number(fragment, "minimum")
        if minimum is not None:
            constraints["ge"] = minimum
        maximum = cls._number(fragment, "maximum")
        if maximum is not None:
            constraints["le"] = maximum
        exclusive_minimum = cls._number(fragment, "exclusiveMinimum")
        if exclusive_minimum is not None:
            constraints["gt"] = exclusive_minimum
        exclusive_maximum = cls._number(fragment, "exclusiveMaximum")
        if exclusive_maximum is not None:
            constraints["lt"] = exclusive_maximum
        multiple_of = cls._number(fragment, "multipleOf")
        if multiple_of is not None:
            constraints["multiple_of"] = multiple_of
        for keyword in ("minLength", "minItems"):
            min_length = cls._count(fragment, keyword)
            if min_length is not None:
                constraints["min_length"] = min_length
        for keyword in ("maxLength", "maxItems"):
            max_length = cls._count(fragment, keyword)
            if max_length is not None:
                constraints["max_length"] = max_length
        pattern = fragment.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str):
                raise TypeError(f"input schema 'pattern' must be a string, got {pattern!r}")
            constraints["pattern"] = pattern
        return constraints

    @staticmethod
    def _number(fragment: Mapping[str, object], keyword: str) -> int | float | None:
        """The numeric bound under *keyword*, or ``None`` when the fragment has none."""
        value = fragment.get(keyword)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"input schema {keyword!r} must be a number, got {value!r}")
        return value

    @staticmethod
    def _count(fragment: Mapping[str, object], keyword: str) -> int | None:
        """The non-negative integer bound under *keyword*, or ``None`` when absent."""
        value = fragment.get(keyword)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"input schema {keyword!r} must be an integer, got {value!r}")
        return value

    @classmethod
    def _unconstrained_type(cls, fragment: Mapping[str, Any], root: Mapping[str, Any]) -> Any:
        if "$ref" in fragment:
            return cls.python_type(cls._resolve_ref(fragment["$ref"], root), root=root)
        if "const" in fragment:
            return Literal[fragment["const"]]
        if "enum" in fragment:
            values = tuple(fragment["enum"])
            return Literal[values] if values else Any
        for combinator in ("anyOf", "oneOf"):
            if combinator in fragment:
                members = [cls.python_type(member, root=root) for member in fragment[combinator]]
                return cls._union(members)
        declared = fragment.get("type")
        nullable = bool(fragment.get("nullable", False))
        if ShapeGuard.is_list(declared):
            members = [cls._typed(fragment, str(name), root) for name in declared]
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
            return list[cls.python_type(items, root=root)] if items is not None else list[Any]
        if name == "object":
            return cls._object_type(fragment, root)
        return Any

    @classmethod
    def _object_type(cls, fragment: Mapping[str, Any], root: Mapping[str, Any]) -> Any:
        properties = fragment.get("properties")
        additional = fragment.get("additionalProperties", True)
        if not ShapeGuard.is_str_keyed_mapping(properties) or not properties:
            value_type = cls.python_type(additional, root=root) if additional is not False else Any
            return dict[str, value_type]
        required = set(fragment.get("required", []))
        fields: dict[str, Any] = {}
        for prop_name, prop_fragment in properties.items():
            prop_type = cls.python_type(prop_fragment, root=root)
            fields[prop_name] = (
                Required[prop_type] if prop_name in required else NotRequired[prop_type]
            )
        # The class name and keys come from the schema at runtime, which the
        # ``TypedDict(name, fields)`` call form cannot take; building the class
        # through ``types.new_class`` is the same ``TypedDict`` subclass.
        typed = types.new_class(
            str(fragment.get("title", "Object")),
            (TypedDict,),
            None,
            functools.partial(JsonSchemaTypeBuilder._typed_dict_namespace, fields),
        )
        # pydantic reads a TypedDict's config from this class attribute.
        typed.__pydantic_config__ = ConfigDict(extra="forbid" if additional is False else "allow")
        return typed

    @staticmethod
    def _typed_dict_namespace(fields: Mapping[str, Any], namespace: dict[str, Any]) -> None:
        """Populate a ``TypedDict`` class body with *fields* as its annotations."""
        namespace["__annotations__"] = dict(fields)

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
