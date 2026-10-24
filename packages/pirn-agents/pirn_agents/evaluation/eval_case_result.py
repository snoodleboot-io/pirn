"""``EvalCaseResult`` — one item's metric scores and pass/fail verdict.

``EvalCaseResult`` is ``Payload[EvalCaseFrame, Mapping[str, float]]`` (PIR-868
pattern, enforced by PIR-874): the frame carries ``item_id``/``passed``/``detail``
and ``data`` is the ``metrics`` mapping of metric name to score. It subclasses
:class:`pirn.core.payload.Payload` directly because ``evaluation/`` does not
import from ``specializations/``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.payload import Payload

from pirn_agents.evaluation.eval_case_frame import EvalCaseFrame


class EvalCaseResult(Payload[EvalCaseFrame, Mapping[str, float]]):
    """The evaluation outcome for a single :class:`EvalItem`.

    The constructor takes ``item_id``, ``metrics`` (metric name to score),
    ``passed`` and ``detail``; read them back as ``metadata.item_id``/
    ``metadata.passed``/``metadata.detail`` and ``data``.
    """

    def __init__(
        self,
        item_id: str,
        metrics: Mapping[str, float],
        passed: bool | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        frame = EvalCaseFrame(
            item_id=item_id,
            passed=passed,
            detail=dict(detail) if detail is not None else {},
        )
        super().__init__(metadata=frame, data=metrics)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["metrics"] = dict(self.data)
        return audit

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EvalCaseResult):
            return NotImplemented
        return self.metadata == other.metadata and self.data == other.data
