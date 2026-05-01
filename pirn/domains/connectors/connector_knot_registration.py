"""Class that registers every Layer-2 connector knot with
:class:`pirn.yaml_loader.knot_registry.KnotRegistry`.

Users invoke ``ConnectorKnotRegistration().register_all()`` once at process
startup so YAML pipelines can refer to connector knots by their registry
name (e.g. ``connectors.object_store_read_source``).

A class — not a free module-level invocation — keeps registration explicit
and re-runnable, and is consistent with the project convention that
behaviour belongs in classes.
"""

from __future__ import annotations

from typing import Any


class ConnectorKnotRegistration:
    """Registers all Layer-2 connector knots with the global KnotRegistry."""

    def __init__(self, prefix: str = "connectors") -> None:
        self._prefix = prefix
        self._registered: list[str] = []

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def registered(self) -> tuple[str, ...]:
        return tuple(self._registered)

    def register_all(self) -> None:
        """Register every shipped Layer-2 knot. Idempotent within a process."""
        from pirn.domains.connectors.knots.database_execute_sink import (
            DatabaseExecuteSink,
        )
        from pirn.domains.connectors.knots.database_query_source import (
            DatabaseQuerySource,
        )
        from pirn.domains.connectors.knots.message_broker_publish_sink import (
            MessageBrokerPublishSink,
        )
        from pirn.domains.connectors.knots.object_store_list_source import (
            ObjectStoreListSource,
        )
        from pirn.domains.connectors.knots.object_store_read_source import (
            ObjectStoreReadSource,
        )
        from pirn.domains.connectors.knots.object_store_write_sink import (
            ObjectStoreWriteSink,
        )

        self._register("object_store_read_source", ObjectStoreReadSource)
        self._register("object_store_write_sink", ObjectStoreWriteSink)
        self._register("object_store_list_source", ObjectStoreListSource)
        self._register("database_query_source", DatabaseQuerySource)
        self._register("database_execute_sink", DatabaseExecuteSink)
        self._register("message_broker_publish_sink", MessageBrokerPublishSink)

    def _register(self, name: str, knot_class: Any) -> None:
        from pirn.yaml_loader.knot_registry import KnotRegistry

        full_name = f"{self._prefix}.{name}"
        if full_name in self._registered:
            # Idempotent within a single instance. We deliberately do NOT
            # consult ``KnotRegistry.has`` here — that would prime an
            # internal sweet-tea cache before our register() calls land,
            # which can make subsequent queries miss freshly-registered
            # entries.
            return
        KnotRegistry.register(full_name, knot_class)
        self._registered.append(full_name)
