"""``EvalReportPayload`` — EvalMetadata bundled with EvalMetrics."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics


class EvalReportPayload(Payload[EvalMetadata, EvalMetrics]):
    """``metadata`` is the :class:`EvalMetadata`; ``data`` is the ``EvalMetrics``."""
