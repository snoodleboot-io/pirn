"""``EvalReportDatabaseDisassembler`` — flatten a :class:`EvalReportPayload` to database rows.

Sits between domain knots that produce an :class:`EvalReportPayload` and a
downstream database-write connector that consumes ``list[tuple[Any, ...]]``.

Algorithm:
    1. Receive ``payload`` (:class:`EvalReportPayload`).
    2. Validate type.
    3. Produce one row per metric score: ``(model_id, metric_name, score)``.
    4. Return the list of rows (pure Python — no thread needed).

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload


class EvalReportDatabaseDisassembler(Disassembler):
    """Flatten an :class:`EvalReportPayload` into database-ready rows.

    Receives a typed :class:`EvalReportPayload` and produces one
    ``(model_id, metric_name, score)`` tuple per entry in ``metrics.scores``.
    Performs no I/O.
    """

    def __init__(
        self,
        *,
        payload: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, _config=_config, **kwargs)

    async def process(
        self,
        payload: EvalReportPayload,
        **_: Any,
    ) -> list[tuple[Any, ...]]:
        """Flatten a :class:`EvalReportPayload` to ``(model_id, metric_name, score)`` rows.

        Args:
            payload: The eval report payload to flatten.

        Returns:
            List of ``(model_id, metric_name, score)`` tuples, one per metric.

        Raises:
            TypeError: If ``payload`` is not an :class:`EvalReportPayload`.
        """
        if not isinstance(payload, EvalReportPayload):
            raise TypeError(
                f"EvalReportDatabaseDisassembler: payload must be EvalReportPayload, "
                f"got {type(payload).__name__}"
            )
        return [
            (payload.report.model_id, metric, float(score))
            for metric, score in payload.metrics.scores.items()
        ]
