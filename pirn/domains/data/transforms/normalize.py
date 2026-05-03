"""``Normalize`` — apply lightweight string cleanup rules per column.

See :class:`pirn.domains.data.transforms.normalize_column_rule.NormalizeColumnRule`
for the rule shape. Rules apply only to ``str`` values; non-string values
pass through untouched. Use :class:`pirn.domains.data.transforms.cast.Cast`
to coerce types separately.
"""

from __future__ import annotations

from typing import Any, Mapping

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
        rules: Mapping[str, NormalizeColumnRule],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._rules: dict[str, NormalizeColumnRule] = dict(rules)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def rules(self) -> Mapping[str, NormalizeColumnRule]:
        return dict(self._rules)

    async def process(self, batch: DataBatch, **_: Any) -> DataBatch:
        """Apply per-column normalization rules to string values and return the updated batch.

        Args:
            batch: The DataBatch whose string column values will be normalized.

        Returns:
            A new DataBatch with normalization rules applied to the configured columns.
        """
        new_rows = tuple(self._normalize_row(row) for row in batch.rows)
        return batch.with_rows(new_rows)

    def _normalize_row(
        self, row: Mapping[str, Any]
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in row.items():
            if key in self._rules and isinstance(value, str):
                out[key] = self._apply(self._rules[key], value)
            else:
                out[key] = value
        return out

    def _apply(self, rule: NormalizeColumnRule, value: str) -> str | None:
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
