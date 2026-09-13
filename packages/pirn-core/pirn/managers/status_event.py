from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pirn.managers.knot_state import KnotState


class StatusEvent(BaseModel):
    """A single state transition for a knot in a run.

    ``extra`` carries structured, span-like metadata a downstream domain wants
    to attach to an ad hoc status event (e.g. an LLM call's model/token/cost/
    latency figures) without inventing a second, core-shaped event stream of
    its own.  ``detail`` stays the short human-readable summary; ``extra`` is
    for machine-readable fields an emitter can render as attributes.  Empty by
    default so every existing engine-issued transition (which never sets it)
    keeps producing byte-identical events.  See ``pirn.engine.emitter_fanout.
    EmitterFanout.emit_status`` for the sanctioned way to emit one of these
    ad hoc, outside the engine's own per-knot lifecycle transitions.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    knot_id: str
    state: KnotState
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detail: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
