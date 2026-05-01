"""``ArrowToLanceSink`` — Tier-4 sink that writes a :class:`pyarrow.Table` to
a Lance dataset on disk.

Sinks have no return value beyond confirming side-effect completion;
this knot writes the table at the configured ``path`` via
:func:`lance.write_dataset` and emits the path as its result so
downstream knots can chain off the materialised dataset location.

The input is annotated as :class:`Any` rather than :class:`pyarrow.Table`
because Pydantic's ``TypeAdapter`` cannot generate a schema for raw
PyArrow tables.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ArrowToLanceSink(Knot):
    """Write a :class:`pyarrow.Table` to a Lance dataset at ``path``."""

    def __init__(
        self,
        *,
        table: Knot,
        path: str,
        mode: str = "create",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(path, str) or not path:
            raise ValueError("ArrowToLanceSink: path must be a non-empty string")
        if mode not in ("create", "append", "overwrite"):
            raise ValueError(
                "ArrowToLanceSink: mode must be one of "
                "{'create', 'append', 'overwrite'}, got "
                f"{mode!r}"
            )
        self._path = path
        self._mode = mode
        super().__init__(table=table, _config=_config, **kwargs)

    @property
    def path(self) -> str:
        return self._path

    @property
    def mode(self) -> str:
        return self._mode

    async def process(self, table: Any, **_: Any) -> str:
        import lance

        lance.write_dataset(table, self._path, mode=self._mode)
        return self._path
