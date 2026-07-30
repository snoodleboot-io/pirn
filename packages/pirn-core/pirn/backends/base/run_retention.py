"""RunRetention — how much history a backend promises to keep."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RunRetention(BaseModel):
    """A backend's declared retention capability.

    The engine needs to know whether a store can absorb an unbounded number of
    runs.  ``LoopSubTapestry`` is the case that forces the question: it models
    *dynamically extensible* pipelines — conversational flows that run until the
    session ends — and records one child run per turn, forever.

    That used to be handled by an ``isinstance(outer_history, InMemoryHistory)``
    check inside the loop node, which skipped recording entirely on the
    in-memory backend.  The intent was right — an ephemeral store genuinely
    cannot absorb that growth — but the consequences were not: ``InMemoryHistory``
    is the *default* backend, so a conversational loop was silently unobservable
    out of the box, and a concrete-type check in the engine cannot see a backend
    core has never heard of.

    Declaring the capability here inverts that.  Recording is always attempted;
    a store that cannot keep everything says so, and keeps a bounded window
    instead.  Observability becomes *bounded* rather than *absent*.  See PIR-765.

    Attributes:
        max_runs: Maximum number of runs the backend retains, oldest evicted
            first once the bound is reached.  ``None`` means unbounded — the
            backend is durable and keeps everything.
    """

    model_config = ConfigDict(frozen=True)

    max_runs: int | None = Field(
        default=None,
        gt=0,
        description="Retained-run ceiling; None for a durable, unbounded backend.",
    )

    @property
    def is_bounded(self) -> bool:
        """True if the backend evicts old runs to stay within a ceiling."""
        return self.max_runs is not None
