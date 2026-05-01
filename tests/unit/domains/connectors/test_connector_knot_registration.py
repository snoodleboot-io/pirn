"""Tests for :class:`ConnectorKnotRegistration`."""

from __future__ import annotations

from pirn.domains.connectors.connector_knot_registration import (
    ConnectorKnotRegistration,
)
from pirn.yaml_loader.knot_registry import KnotRegistry


class TestConnectorKnotRegistration:
    def test_register_all_registers_each_layer2_knot(self) -> None:
        registration = ConnectorKnotRegistration(prefix="connectors_test")
        registration.register_all()

        registered = registration.registered
        # Six knots ship in this PR.
        assert len(registered) == 6
        for name in (
            "connectors_test.object_store_read_source",
            "connectors_test.object_store_write_sink",
            "connectors_test.object_store_list_source",
            "connectors_test.database_query_source",
            "connectors_test.database_execute_sink",
            "connectors_test.message_broker_publish_sink",
        ):
            assert name in registered
            assert KnotRegistry.has(name)

    def test_register_all_is_idempotent(self) -> None:
        registration = ConnectorKnotRegistration(prefix="connectors_idempotent")
        registration.register_all()
        first = registration.registered
        # Second call should not double-register.
        registration.register_all()
        assert registration.registered == first

    def test_default_prefix_is_connectors(self) -> None:
        registration = ConnectorKnotRegistration()
        assert registration.prefix == "connectors"
