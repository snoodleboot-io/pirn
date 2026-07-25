"""``LoggingSink`` — an :class:`ObservabilitySink` that writes spans to stdlib logging."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn_agents.observability.observability_sink import ObservabilitySink
from pirn_agents.observability.span import Span


class LoggingSink(ObservabilitySink):
    """Emit each span lifecycle transition as a structured log record.

    Backend-free: it uses only the standard library :mod:`logging`, so it needs
    no extra and is safe to wire in any environment. Start/finish/event map to
    ``debug``/``info`` records carrying the span id, kind, and — on finish — the
    status and duration, so a run's span tree is reconstructable from logs alone.
    """

    def __init__(self, logger: logging.Logger | None = None, *, level: int = logging.INFO) -> None:
        """Bind to a logger (defaults to this module's) and emit at ``level``."""
        self._logger = logger if logger is not None else logging.getLogger(__name__)
        self._level = level

    def on_start(self, span: Span) -> None:
        """Log span open at ``debug``."""
        self._logger.debug(
            "span start id=%s kind=%s name=%s parent=%s",
            span.span_id,
            span.kind.value,
            span.name,
            span.parent_id,
        )

    def on_event(self, span: Span, name: str, attributes: Mapping[str, Any]) -> None:
        """Log a span event at ``debug``."""
        self._logger.debug(
            "span event id=%s name=%s attrs=%s", span.span_id, name, dict(attributes)
        )

    def on_finish(self, span: Span) -> None:
        """Log span close at the configured level with status and duration."""
        self._logger.log(
            self._level,
            "span finish id=%s kind=%s name=%s status=%s duration=%s attrs=%s",
            span.span_id,
            span.kind.value,
            span.name,
            span.status.value,
            span.duration,
            dict(span.attributes),
        )
