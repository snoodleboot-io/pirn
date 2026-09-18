"""``DocumentIngestFold`` — turn one document's ETL ``Result`` into an outcome.

Internal knot for
:class:`~pirn_agents.specializations.document_processing.ingestion_runner.IngestionRunner`'s
fan-out. Wired with ``error_policy=RECEIVE_ERRORS`` over that document's
:class:`~pirn_agents.specializations.document_processing.document_ingest.DocumentIngest`,
so ``outcome`` here is the ETL's raw ``Ok``/``Err``/``Skipped``.

Before PIR-873 ``DocumentIngest`` caught its own exceptions and returned an
errored :class:`DocumentOutcome` built from ``str(exc)``. That hand-rolled the
engine's own ``Err``: the exception never reached ``ExceptionRecord``, so the
type and the traceback were thrown away and the failed document was recorded
in history as a *successful* knot whose value happened to carry a message.
Letting the ETL raise and folding the engine's ``Result`` here keeps the
isolation (one bad document still never fails its siblings or the run) while
the failure is recorded with its type and traceback like any other.

Algorithm:
    1. ``Ok`` — carry the ETL's :class:`DocumentOutcome` through unchanged.
    2. ``Err`` — build an errored outcome from the record's ``exc_type`` and
       ``message``; the full traceback stays on the run's ``ExceptionRecord``.
    3. ``Skipped`` — build an errored outcome naming the skip reason, so a
       document that never ran is reported rather than silently counted as
       processed.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped

from pirn_agents.specializations.document_processing.document_outcome import DocumentOutcome


class DocumentIngestFold(Knot):
    """Fold one document's ETL ``Result`` into a :class:`DocumentOutcome`."""

    def __init__(
        self,
        *,
        source_id: Knot | str,
        outcome: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(source_id=source_id, outcome=outcome, _config=_config, **kwargs)

    async def process(
        self,
        source_id: str,
        outcome: Ok[DocumentOutcome] | Err | Skipped,
        **_: Any,
    ) -> DocumentOutcome:
        """Report this document's ETL outcome.

        Args:
            source_id: The document the ETL ran for.
            outcome: That ETL knot's ``Result``.

        Returns:
            The ETL's own :class:`DocumentOutcome` on success, else an errored
            one naming the failure or the skip reason.
        """
        if isinstance(outcome, Err):
            record = outcome.record
            return DocumentOutcome(
                source_id=source_id, error=f"{record.exc_type}: {record.message}"
            )
        if isinstance(outcome, Skipped):
            return DocumentOutcome(source_id=source_id, error=f"skipped: {outcome.reason}")
        return outcome.value
