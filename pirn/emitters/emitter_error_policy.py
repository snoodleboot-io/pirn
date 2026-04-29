from __future__ import annotations

from enum import StrEnum


class EmitterErrorPolicy(StrEnum):
    """How the engine reacts when an emitter raises during a run.

    * WARN — log a warning and continue (default).
    * IGNORE — swallow the error silently.
    * RAISE — propagate the exception, aborting run finalisation.
    """

    WARN = "warn"
    IGNORE = "ignore"
    RAISE = "raise"
