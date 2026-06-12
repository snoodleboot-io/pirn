"""Tests for :class:`pirn.connectors.streaming.azure_servicebus_config.AzureServiceBusConfig`.
"""

from __future__ import annotations

import unittest

from pirn.connectors.streaming.azure_servicebus_config import AzureServiceBusConfig


class TestAzureServiceBusConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = AzureServiceBusConfig()
        self.assertIsNone(cfg.connection_string)
        self.assertIsNone(cfg.namespace)

    def test_construct_with_connection_string(self) -> None:
        cfg = AzureServiceBusConfig(
            connection_string="Endpoint=sb://ns.servicebus.windows.net/;SharedAccessKeyName=k;SharedAccessKey=v;"
        )
        self.assertIsNotNone(cfg.connection_string)

    def test_construct_with_namespace(self) -> None:
        cfg = AzureServiceBusConfig(namespace="my-namespace.servicebus.windows.net")
        self.assertEqual(cfg.namespace, "my-namespace.servicebus.windows.net")

    def test_sensitive_fields(self) -> None:
        self.assertIn("connection_string", AzureServiceBusConfig.sensitive_fields)

    def test_repr_redacts_connection_string(self) -> None:
        cfg = AzureServiceBusConfig(connection_string="Endpoint=sb://ns.servicebus.windows.net/;SharedAccessKey=secret;")
        text = repr(cfg)
        self.assertNotIn("secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = AzureServiceBusConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.namespace = "mutated"  # type: ignore[misc]
