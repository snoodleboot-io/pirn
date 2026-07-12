"""``TypedMemoryValidator`` — validate a record against the typed memory schema.

The S5 validation knot: given a candidate object, it enforces the typed schema —
the value is a :class:`~pirn_agents.memory_management.memory_record.MemoryRecord`
(so ``kind``, ``provenance``, ``importance`` were already checked in
``__post_init__``) and, optionally, that its kind is one of a caller-supplied
allowed subset. It returns the validated record unchanged so it can sit inline on
a store's write path (``__init__``\\ →\\ ``process`` + isinstance validation),
giving ``memory_patterns/`` producers a single, typed gate.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_management.memory_kind import MemoryKind, is_memory_kind
from pirn_agents.memory_management.memory_record import MemoryRecord


class TypedMemoryValidator(Knot):
    """Validates that a value is a well-formed :class:`MemoryRecord`."""

    def __init__(
        self,
        *,
        record: Knot | MemoryRecord,
        allowed_kinds: Knot | Sequence[MemoryKind] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            record=record,
            allowed_kinds=allowed_kinds,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        record: MemoryRecord,
        allowed_kinds: Sequence[MemoryKind] | None = None,
        **_: Any,
    ) -> MemoryRecord:
        """Return ``record`` unchanged after validating the typed schema.

        Args:
            record: The candidate memory record.
            allowed_kinds: Optional subset of kinds the record must belong to;
                ``None`` allows every :data:`MemoryKind`.

        Returns:
            The validated :class:`MemoryRecord`.

        Raises:
            TypeError: If ``record`` is not a MemoryRecord.
            ValueError: If ``allowed_kinds`` holds a non-kind value, or the
                record's kind is outside the allowed subset.
        """
        if not isinstance(record, MemoryRecord):
            raise TypeError(
                f"TypedMemoryValidator: record must be a MemoryRecord, got {type(record).__name__}"
            )
        if allowed_kinds is None:
            return record
        allowed = tuple(allowed_kinds)
        for candidate in allowed:
            if not is_memory_kind(candidate):
                raise ValueError(
                    f"TypedMemoryValidator: allowed_kinds holds a non-kind {candidate!r}"
                )
        if record.kind not in allowed:
            raise ValueError(
                f"TypedMemoryValidator: record kind {record.kind!r} not in allowed {allowed!r}"
            )
        return record
