"""``BatchItemStatus`` — terminal disposition of a single batch item."""

from __future__ import annotations

from enum import Enum


class BatchItemStatus(str, Enum):  # noqa: UP042 - str-mixin form is required for stable serialisation
    """Outcome classification for a :class:`BatchItemResult`.

    .. deprecated::
        ADR agents-speaks-core WS2: this is one of the outcome enums the ADR
        wants collapsed onto core's ``Ok | Err | Skipped`` ``Result`` (see
        :meth:`~pirn_agents.batch.batch_item_result.BatchItemResult.to_result` /
        :meth:`~pirn_agents.batch.batch_item_result.BatchItemResult.from_result`).
        It is kept, unchanged, for one deprecation cycle because ``MapAgent``'s
        scheduling (a separate workstream) still produces and consumes it
        directly, and because it has one member — ``TIMEOUT`` — that
        ``Result`` cannot express structurally (only via ``Err.record.exc_type``).
        Prefer ``to_result()`` when writing new code that only needs to know
        success/failure/skip, not the timeout distinction.

    String-valued so the member serialises to a stable, human-readable token
    that survives round-trips through a result sink or checkpoint without
    depending on enum member ordering.

    Members
    -------
    OK:
        The agent ran to completion and produced an output for the item.
    ERROR:
        The agent raised (or a retry budget was exhausted); ``error`` carries
        the detail. A single item's error never aborts its siblings.
    TIMEOUT:
        The per-item time budget elapsed before the agent finished.
    SKIPPED:
        The item was already completed in a prior run and was skipped on resume.
    """

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
