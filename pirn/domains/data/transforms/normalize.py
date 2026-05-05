"""``Normalize`` — apply lightweight string cleanup rules per column.

See :class:`pirn.domains.data.transforms.normalize_column_rule.NormalizeColumnRule`
for the rule shape. Rules apply only to ``str`` values; non-string values
pass through untouched. Use :class:`pirn.domains.data.transforms.cast.Cast`
to coerce types separately.

Algorithm:
    1. Validate ``rules``: must be a non-empty ``Mapping[str, NormalizeColumnRule]``
       with non-empty string keys.
    2. For each row in the batch, process every column value:

       a. If the column is not in ``rules`` or the value is not a ``str``,
          pass it through unchanged.
       b. Otherwise apply the rule steps in order:

          i.  If ``strip_whitespace`` is set, collapse internal whitespace
              runs and strip leading/trailing whitespace.
          ii. If ``case`` is set (``"lower"``, ``"upper"``, or ``"title"``),
              apply the corresponding case transformation.
          iii. If ``null_tokens`` is set, compare the processed value against
               the token list (case-insensitively by default). If it matches,
               replace the value with ``None``.

    3. Return a new batch with the normalised rows; the schema is unchanged.

    ```text
    for row in rows:
        for col, value in row:
            if col in rules and isinstance(value, str):
                value = apply_rule(rules[col], value)
            emit col: value
    ```

References:
    [1] Python ``str`` methods (``split``, ``join``, ``lower``, ``upper``,
        ``title``) — all normalisation steps delegate to these builtins:
        https://docs.python.org/3/library/stdtypes.html#string-methods
    [2] dbt ``accepted_values`` and ``not_null`` generic tests — community
        patterns for null-sentinel replacement and case normalisation:
        https://docs.getdbt.com/docs/build/data-tests
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.transforms.normalize_column_rule import NormalizeColumnRule


class Normalize(Knot):
    """Apply per-column :class:`NormalizeColumnRule` instances."""

    def __init__(
        self,
        *,
        batch: Knot,
        rules: Knot | Mapping[str, NormalizeColumnRule],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, rules=rules, _config=_config, **kwargs)

    async def process(
        self,
        batch: DataBatch,
        rules: Any,
        **_: Any,
    ) -> DataBatch:
        """Apply per-column normalization rules to string values and return the updated batch.

        Args:
            batch: The DataBatch whose string column values will be normalized.
            rules: Mapping of column name to NormalizeColumnRule.

        Returns:
            A new DataBatch with normalization rules applied to the configured columns.
        """
        if not isinstance(rules, Mapping) or not rules:
            raise TypeError(
                "Normalize: rules must be a non-empty Mapping[column, "
                "NormalizeColumnRule]"
            )
        for column, rule in rules.items():
            if not isinstance(column, str) or not column:
                raise TypeError("Normalize: rule keys must be non-empty strings")
            if not isinstance(rule, NormalizeColumnRule):
                raise TypeError(
                    f"Normalize: rules[{column!r}] must be a NormalizeColumnRule, "
                    f"got {type(rule).__name__}"
                )
        rules_dict: dict[str, NormalizeColumnRule] = dict(rules)
        new_rows = tuple(self._normalize_row(row, rules_dict) for row in batch.rows)
        return batch.with_rows(new_rows)

    @staticmethod
    def _normalize_row(
        row: Mapping[str, Any],
        rules: dict[str, NormalizeColumnRule],
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in row.items():
            if key in rules and isinstance(value, str):
                out[key] = Normalize._apply(rules[key], value)
            else:
                out[key] = value
        return out

    @staticmethod
    def _apply(rule: NormalizeColumnRule, value: str) -> str | None:
        if rule.strip_whitespace:
            value = " ".join(value.split())
        if rule.case == "lower":
            value = value.lower()
        elif rule.case == "upper":
            value = value.upper()
        elif rule.case == "title":
            value = value.title()
        if rule.null_tokens:
            comparison = value if rule.null_tokens_case_sensitive else value.lower()
            tokens = (
                rule.null_tokens
                if rule.null_tokens_case_sensitive
                else tuple(t.lower() for t in rule.null_tokens)
            )
            if comparison in tokens:
                return None  # type: ignore[return-value]
        return value
