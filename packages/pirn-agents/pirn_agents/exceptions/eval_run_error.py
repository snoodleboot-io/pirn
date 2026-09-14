"""``EvalRunError`` — an eval run in which some item's evaluation failed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.exceptions.pirn_error import PirnError

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class EvalRunError(PirnError):
    """Raised by :meth:`~pirn_agents.evaluation.run_eval.RunEval.run` when an item failed.

    An item's target call, a metric or its threshold check raising is that
    item knot's ``Err``; the report cannot be assembled without every item, so
    the runner raises this naming each failure. The run itself — every item's
    lineage row and recorded value — is still in the history it ran against.

    Attributes
    ----------
    run_result:
        The eval run, for inspection of its lineage and exceptions.
    """

    def __init__(self, run_result: RunResult) -> None:
        self.run_result = run_result
        causes = "; ".join(
            f"{record.knot_id}: {record.exc_type}: {record.message}"
            for record in run_result.exceptions
        )
        super().__init__(
            f"eval run {run_result.run_id!r} failed with "
            f"{len(run_result.exceptions)} exception(s)" + (f" [{causes}]" if causes else "")
        )
