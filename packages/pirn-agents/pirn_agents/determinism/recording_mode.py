"""``RecordingMode`` — how a :class:`CassetteRecorder` treats each I/O call."""

from __future__ import annotations

from enum import Enum


class RecordingMode(str, Enum):  # noqa: UP042 - str-mixin for stable serialisation
    """The three cassette postures for a unit of non-deterministic I/O.

    String-valued for stable, human-readable serialisation independent of enum
    ordering.

    Members
    -------
    RECORD:
        Execute the live call and append its result to the cassette.
    REPLAY:
        Serve the recorded result for the call's key with no live I/O; a missing
        entry is an error, never a silent live call.
    PASSTHROUGH:
        Execute the live call and record nothing (behaves like no recorder).
    """

    RECORD = "record"
    REPLAY = "replay"
    PASSTHROUGH = "passthrough"
