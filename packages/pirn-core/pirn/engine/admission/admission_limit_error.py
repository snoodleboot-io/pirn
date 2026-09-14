"""Raised when a gate's limit cannot be adjusted the way it was asked to."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class AdmissionLimitError(PirnError):
    """``Admission.set_limit`` was asked for something the gate cannot do.

    The group is not one the run's ``ConcurrencyLimits`` define (groups
    cannot be added mid-run: the ready queue and the fail-fast group check
    were sized at run start), the limit is below one, or the gate is the
    unbounded one, which enforces no limits at all — a run that wants its
    caps adjusted at runtime starts with ``ConcurrencyLimits``.
    """
