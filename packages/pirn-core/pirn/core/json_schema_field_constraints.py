"""``JsonSchemaFieldConstraints`` — the ``pydantic.Field`` bounds a JSON-schema fragment declares."""

from __future__ import annotations

from typing import TypedDict


class JsonSchemaFieldConstraints(TypedDict, total=False):
    """Keyword arguments for ``pydantic.Field`` built from JSON-schema bound keywords.

    ``JsonSchemaTypeBuilder`` fills it from ``minimum`` / ``maximum`` /
    ``exclusiveMinimum`` / ``exclusiveMaximum`` / ``multipleOf`` (numbers),
    ``minLength`` / ``minItems`` / ``maxLength`` / ``maxItems`` (counts) and
    ``pattern``, then unpacks it into ``Field(**constraints)``.
    """

    ge: int | float
    le: int | float
    gt: int | float
    lt: int | float
    multiple_of: int | float
    min_length: int
    max_length: int
    pattern: str
