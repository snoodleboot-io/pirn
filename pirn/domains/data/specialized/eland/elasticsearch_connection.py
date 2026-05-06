"""``ElasticsearchConnection`` — pydantic-opaque wrapper for an Elasticsearch client.

An ``elasticsearch.Elasticsearch`` client is a live, stateful object holding
open HTTP connections to an Elasticsearch cluster. Pydantic cannot introspect
or serialise it. This thin wrapper inherits
:class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` so it receives an
opaque ``isinstance`` schema, allowing it to travel between Knots in the
pirn graph without triggering pydantic schema generation errors.

The wrapped client is accessed via the read-only :attr:`client` property.
"""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ElasticsearchConnection(PirnOpaqueValue):
    """Pydantic-opaque holder for an Elasticsearch client.

    Pass this through the pirn graph and unwrap with ``.client`` in any
    consuming Knot's ``process()`` method.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        return self._client

    def _pirn_audit_dict(self) -> Any:
        return f"<ElasticsearchConnection@{id(self._client):x}>"
