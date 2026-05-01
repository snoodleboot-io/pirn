"""``AggregateSpec`` — one aggregation rule consumed by
:class:`pirn.domains.data.transforms.aggregate.Aggregate`.

``source`` names the input column whose values feed the aggregation.
``function`` is one of the supported aggregation names; the validation
list lives on :meth:`AggregateSpec._allowed_functions` rather than as a
module-level constant so the rule for what's permitted travels with the
class.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AggregateSpec:
    """Defines one aggregation: which input column, which function."""

    source: str
    function: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("AggregateSpec.source must be a non-empty string")
        allowed = self._allowed_functions()
        if self.function not in allowed:
            raise ValueError(
                f"AggregateSpec.function must be one of {list(allowed)}, "
                f"got {self.function!r}"
            )

    @classmethod
    def _allowed_functions(cls) -> tuple[str, ...]:
        return (
            "sum",
            "mean",
            "min",
            "max",
            "count",
            "count_distinct",
            "first",
            "last",
        )
