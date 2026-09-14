"""``NestedAuditValue`` — an opaque value whose audit form folds in nested opaque values.

A specialization frame or result (``ReWooFrame``, ``WorkerTaskResult``, ...) builds
its :meth:`~pirn.core.pirn_opaque_value.PirnOpaqueValue._pirn_audit_dict` from the
audit forms of the opaque values it carries (tool calls, tool results, agent
responses, attempts). ``_pirn_audit_dict`` is ``PirnOpaqueValue``'s protected
contract: it is called through the ``PirnOpaqueValue`` declaration, from a class that
is itself a ``PirnOpaqueValue``, and dispatches to each nested value's own override.

References:
    - :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class NestedAuditValue(PirnOpaqueValue):
    """``PirnOpaqueValue`` base for values whose audit form embeds nested opaque values."""

    @staticmethod
    def _audit_form(value: PirnOpaqueValue) -> Any:
        """Return ``value``'s audit form (its own ``_pirn_audit_dict`` override).

        Args:
            value: A nested opaque value.

        Returns:
            The primitive form ``value`` emits for lineage and hashing.
        """
        return value._pirn_audit_dict()

    @staticmethod
    def _audit_forms(values: Iterable[PirnOpaqueValue]) -> list[Any]:
        """Return the audit form of every nested value, in order.

        Args:
            values: The nested opaque values.

        Returns:
            One audit form per value.
        """
        return [NestedAuditValue._audit_form(value) for value in values]
