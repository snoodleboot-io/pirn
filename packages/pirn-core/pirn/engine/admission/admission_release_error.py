"""Raised when a gate is handed back capacity it is not holding."""

from __future__ import annotations

from pirn.exceptions.pirn_error import PirnError


class AdmissionReleaseError(PirnError):
    """A ticket was released that the gate did not issue, or released twice.

    Either would corrupt the gate's counters -- a slot freed twice lets one
    more knot in than the limit allows -- so the gate refuses loudly instead.
    It always indicates a scheduler bug, never a user error.
    """
