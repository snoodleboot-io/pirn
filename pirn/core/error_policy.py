from __future__ import annotations

from enum import StrEnum


class ErrorPolicy(StrEnum):
    """How a knot reacts when one or more parents produced Err or Skipped.

    * SKIP_IF_PARENT_FAILED — if any parent failed or was skipped, this
      knot is skipped.  The default.
    * RECEIVE_ERRORS — the knot's process is called with the parents'
      Result values directly; the author handles Err and Skipped cases.
    * REQUIRE_ALL_PARENTS — strict: any failed or skipped parent causes
      this knot itself to fail with a deterministic Err.
    """

    SKIP_IF_PARENT_FAILED = "skip_if_parent_failed"
    RECEIVE_ERRORS = "receive_errors"
    REQUIRE_ALL_PARENTS = "require_all_parents"
