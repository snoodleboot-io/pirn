"""``PyarrowAggregate`` — Tier-2 group-by + aggregation via
:meth:`pyarrow.Table.group_by` and the ``pyarrow.compute`` aggregation
kernels.

The caller supplies:

* ``by``: sequence of column names to group on, and
* ``aggs``: mapping of *output column name* → ``(input_column,
  aggregation_function)`` where ``aggregation_function`` is one of the
  string suffixes supported by ``pyarrow.compute`` group aggregations
  (``"sum"``, ``"min"``, ``"max"``, ``"mean"``, ``"count"``,
  ``"count_distinct"``, ``"first"``, ``"last"``, ``"any"``, ``"all"``).

PyArrow names aggregate output columns ``"<input>_<fn>"``. After running
the aggregation we rename to the caller-provided output names, keeping
the by-columns at the front in their original order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class PyarrowAggregate(Knot):
    """Group rows by ``by`` and apply PyArrow aggregation kernels."""

    _allowed_functions: ClassVar[frozenset[str]] = frozenset(
        {
            "sum",
            "min",
            "max",
            "mean",
            "count",
            "count_distinct",
            "first",
            "last",
            "any",
            "all",
        }
    )

    def __init__(
        self,
        *,
        batch: Knot,
        by: Knot | Sequence[str],
        aggs: Knot | Mapping[str, tuple[str, str]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, by=by, aggs=aggs, _config=_config, **kwargs)

    async def process(
        self,
        batch: PyarrowDataBatch,
        by: Any,  # Sequence[str] — deferred so string rejection fires in process(), not pydantic
        aggs: Any,  # Mapping[str, tuple[str, str]] — deferred so non-Mapping rejection fires here
        **_: Any,
    ) -> PyarrowDataBatch:
        """Group the table by the configured columns and apply PyArrow aggregation kernels.

        Args:
            batch: The upstream PyarrowDataBatch to aggregate.
            by: Column names to group on.
            aggs: Mapping of output column name to (input_column, aggregation_function).

        Returns:
            A new PyarrowDataBatch containing one row per group with the caller-named columns.
        """
        if isinstance(by, (str, bytes)):
            raise TypeError(
                "PyarrowAggregate: by must be a sequence of column names, not a string"
            )
        IdentifierValidator.validate_columns("PyarrowAggregate.by", by)
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "PyarrowAggregate: aggs must be a non-empty Mapping"
                "[output_name, (input_column, aggregation_function)]"
            )
        for output, spec in aggs.items():
            IdentifierValidator.validate_column(
                "PyarrowAggregate: output column", output
            )
            if (
                not isinstance(spec, tuple)
                or len(spec) != 2
                or not isinstance(spec[0], str)
                or not isinstance(spec[1], str)
            ):
                raise TypeError(
                    f"PyarrowAggregate: aggs[{output!r}] must be a tuple "
                    "(input_column, aggregation_function)"
                )
            input_column, function_name = spec
            IdentifierValidator.validate_column(
                f"PyarrowAggregate: aggs[{output!r}] input_column",
                input_column,
            )
            if function_name not in self._allowed_functions:
                raise ValueError(
                    f"PyarrowAggregate: aggs[{output!r}] function "
                    f"{function_name!r} is not supported; allowed: "
                    f"{sorted(self._allowed_functions)}"
                )

        agg_specs = [
            (input_column, function_name)
            for input_column, function_name in aggs.values()
        ]
        aggregated = batch.table.group_by(list(by)).aggregate(agg_specs)
        # PyArrow's aggregate emits the by-columns first followed by the
        # aggregated columns in input order, named ``"<input>_<fn>"``.
        # Rename the trailing block to the caller-provided output names.
        target_names = list(by) + list(aggs.keys())
        renamed = aggregated.rename_columns(target_names)
        return batch.with_table(renamed)
