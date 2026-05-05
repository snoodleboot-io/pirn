"""``ArrowToLanceSink`` — Tier-4 sink that writes a :class:`pyarrow.Table` to
a Lance dataset on disk.

Sinks have no return value beyond confirming side-effect completion;
this knot writes the table at the configured ``path`` via
:func:`lance.write_dataset` and emits the path as its result so
downstream knots can chain off the materialised dataset location.

The input is annotated as :class:`Any` rather than :class:`pyarrow.Table`
because Pydantic's ``TypeAdapter`` cannot generate a schema for raw
PyArrow tables.

Algorithm:
    1. Validate that ``path`` is a non-empty string and ``mode`` is one
       of ``{'create', 'append', 'overwrite'}``.
    2. Call ``lance.write_dataset(table, path, mode=mode)`` to materialise
       the PyArrow table as a Lance dataset on the local (or remote)
       filesystem.
    3. Return ``path`` so downstream knots can reference the written
       dataset location.

References:
    [1] Lance ``write_dataset`` API:
        https://lancedb.github.io/lance/api/python/lance.html#lance.write_dataset
    [2] Lance dataset format — columnar, versioned, optimised for ML
        workloads: https://lancedb.github.io/lance/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sink import Sink


class ArrowToLanceSink(Sink):
    """Write a :class:`pyarrow.Table` to a Lance dataset at ``path``."""

    def __init__(
        self,
        *,
        table: Knot,
        path: Knot | str,
        mode: Knot | str = "create",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            table=table,
            path=path,
            mode=mode,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        table: Any,
        path: Any,
        mode: Any = "create",
        **_: Any,
    ) -> str:
        if not isinstance(path, str) or not path:
            raise ValueError("ArrowToLanceSink: path must be a non-empty string")
        if mode not in ("create", "append", "overwrite"):
            raise ValueError(
                "ArrowToLanceSink: mode must be one of "
                "{'create', 'append', 'overwrite'}, got "
                f"{mode!r}"
            )
        import lance

        lance.write_dataset(table, path, mode=mode)
        return path
