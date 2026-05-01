"""Tabular schema declaration used across ``pirn.domains.data``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class DataSchema:
    """Declarative schema for a tabular :class:`DataBatch`.

    Attributes
    ----------
    columns:
        Mapping of column name → expected Python type. Insertion order is
        the canonical column order.
    primary_keys:
        Subset of ``columns`` keys; non-empty for any sink that performs
        upsert or dedup operations.
    nullable:
        Subset of ``columns`` keys whose values may be ``None``.
    """

    columns: Mapping[str, type] = field(default_factory=dict)
    primary_keys: tuple[str, ...] = ()
    nullable: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        unknown_pks = [k for k in self.primary_keys if k not in self.columns]
        if unknown_pks:
            raise ValueError(
                f"primary_keys reference unknown columns: {unknown_pks}"
            )
        unknown_nullable = [k for k in self.nullable if k not in self.columns]
        if unknown_nullable:
            raise ValueError(
                f"nullable references unknown columns: {unknown_nullable}"
            )

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.columns.keys())

    def is_nullable(self, column: str) -> bool:
        """Return True if ``column`` is permitted to hold ``None``."""
        return column in self.nullable

    def with_columns(self, columns: Mapping[str, type]) -> "DataSchema":
        """Return a new schema with the given columns merged in."""
        merged = dict(self.columns)
        merged.update(columns)
        return DataSchema(
            columns=merged,
            primary_keys=self.primary_keys,
            nullable=self.nullable,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Treat as opaque: ``columns`` holds Python ``type`` objects which
        pydantic's default JSON serialiser can't dump. Pirn IO validation
        just checks ``isinstance(value, DataSchema)``; content-addressing
        serialises via a stable summary that converts types to their names.
        """
        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: {
                    "columns": {k: t.__name__ for k, t in v.columns.items()},
                    "primary_keys": list(v.primary_keys),
                    "nullable": list(v.nullable),
                },
                when_used="always",
            ),
        )
