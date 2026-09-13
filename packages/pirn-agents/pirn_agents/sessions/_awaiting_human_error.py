"""``_AwaitingHumanError`` — sentinel converted to ``Skipped`` by :class:`SuspendingApprovalCheck`."""

from __future__ import annotations


class _AwaitingHumanError(Exception):
    """Raised by :meth:`SuspendingApprovalCheck.process` to signal a suspend.

    Never escapes to a caller: ``SuspendingApprovalCheck.__call__`` catches
    the ``Err`` this produces and converts it to
    ``Skipped(reason="awaiting_human")``, mirroring how
    ``pirn.nodes.gate.gate.Gate`` converts ``_GateClosedError`` to
    ``Skipped(reason="gate_closed")``.
    """
