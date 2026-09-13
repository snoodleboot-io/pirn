"""Log emitter — writes structured records to the stdlib logging module."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pirn.emitters.emitter import Emitter

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage
    from pirn.core.run_result import RunResult
    from pirn.managers.status_event import StatusEvent


class LogEmitter(Emitter):
    """Emits run events to a stdlib ``logging.Logger``.

    Format is JSON-style ``extra=`` fields so log aggregators (Loki,
    Splunk, CloudWatch) can parse the records.  Set
    ``with_payload=True`` to include the full ``RunResult`` /
    ``KnotLineage`` JSON in the log record (verbose, but useful for
    debugging).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        with_payload: bool = False,
    ) -> None:
        """Initialise the emitter.

        Args:
            logger: Logger to write to.  Defaults to the ``pirn``
                root logger when ``None``.
            with_payload: When ``True``, the full JSON-serialised
                ``RunResult`` or ``KnotLineage`` is included in each
                log record under the ``pirn_payload`` extra key.
                Useful for debugging; may be verbose in production.
        """
        self._log = logger or logging.getLogger("pirn")
        self._with_payload = with_payload

    async def on_status(self, event: StatusEvent) -> None:
        """Logs a knot state-transition event at INFO level.

        When ``event.extra`` carries structured metadata — an ad hoc event a
        downstream domain emitted for a sub-step the engine has no lifecycle
        for (an LLM call, a tool call, a retrieval step) — it is included
        under the ``pirn_extra`` key so it is queryable the same way
        ``pirn_detail`` already is, without changing the log message itself.

        Args:
            event: The status event to log.
        """
        extra_map = event.extra if isinstance(getattr(event, "extra", None), dict) else {}
        self._log.info(
            "knot %s: %s",
            event.knot_id,
            event.state.value,
            extra={
                "pirn_event": "status",
                "pirn_run_id": event.run_id,
                "pirn_knot_id": event.knot_id,
                "pirn_state": event.state.value,
                "pirn_detail": event.detail,
                "pirn_extra": dict(extra_map) if extra_map else None,
            },
        )

    async def on_lineage(self, record: KnotLineage) -> None:
        """Logs a lineage record at INFO level with structured extra fields.

        When ``with_payload=True`` the full JSON is included under the
        ``pirn_payload`` key.

        Args:
            record: The knot lineage record to log.
        """
        extra = {
            "pirn_event": "lineage",
            "pirn_run_id": record.run_id,
            "pirn_knot_id": record.knot_id,
            "pirn_outcome": record.outcome,
            "pirn_output_hash": record.output_hash,
            "pirn_duration_ms": record.duration_ms,
        }
        if self._with_payload:
            extra["pirn_payload"] = record.model_dump_json()
        self._log.info(
            "lineage %s/%s: %s (%.1fms)",
            record.run_id,
            record.knot_id,
            record.outcome,
            record.duration_ms,
            extra=extra,
        )

    async def on_run_result(self, result: RunResult) -> None:
        """Logs the final run result at INFO (success) or ERROR (failure) level.

        When ``with_payload=True`` the full JSON is included under the
        ``pirn_payload`` key.

        Args:
            result: The completed run result to log.
        """
        extra = {
            "pirn_event": "run_result",
            "pirn_run_id": result.run_id,
            "pirn_succeeded": result.succeeded,
            "pirn_dispatcher": result.dispatcher,
            "pirn_duration_seconds": result.duration_seconds,
        }
        if self._with_payload:
            extra["pirn_payload"] = result.model_dump_json()
        level = logging.INFO if result.succeeded else logging.ERROR
        self._log.log(
            level,
            "run %s: %s in %.2fs",
            result.run_id,
            "succeeded" if result.succeeded else "FAILED",
            result.duration_seconds,
            extra=extra,
        )
