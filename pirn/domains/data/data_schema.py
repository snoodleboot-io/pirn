"""Tabular schema declaration used across ``pirn.domains.data``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class DataSchema(PirnOpaqueValue):
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
            raise ValueError(f"primary_keys reference unknown columns: {unknown_pks}")
        unknown_nullable = [k for k in self.nullable if k not in self.columns]
        if unknown_nullable:
            raise ValueError(f"nullable references unknown columns: {unknown_nullable}")

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.columns.keys())

    def is_nullable(self, column: str) -> bool:
        """Return True if ``column`` is permitted to hold ``None``."""
        return column in self.nullable

    def with_columns(self, columns: Mapping[str, type]) -> DataSchema:
        """Return a new schema with the given columns merged in."""
        merged = dict(self.columns)
        merged.update(columns)
        return DataSchema(
            columns=merged,
            primary_keys=self.primary_keys,
            nullable=self.nullable,
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Flatten to a primitive dict for pydantic serialisation.

        ``columns`` holds Python ``type`` objects which pydantic's
        default JSON serialiser can't dump; here we convert each type
        to its name. Pirn IO validation just checks
        ``isinstance(value, DataSchema)``; content-addressing serialises
        via this stable summary.
        """
        return {
            "columns": {k: t.__name__ for k, t in self.columns.items()},
            "primary_keys": list(self.primary_keys),
            "nullable": list(self.nullable),
        }

    def __pirn_canonical__(self) -> dict[str, Any]:
        """Sanctioned canonical form for :func:`pirn.core.hashing.content_hash`.

        Mirrors :meth:`_pirn_audit_dict` but is the explicit hook the
        hasher prefers. Keeping both methods avoids forcing every
        existing pydantic-serialisation call site through the canonical
        path (and vice versa).
        """
        return {
            "columns": {name: column_type.__name__ for name, column_type in self.columns.items()},
            "primary_keys": list(self.primary_keys),
            "nullable": list(self.nullable),
        }
