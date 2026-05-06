"""Tests for :class:`pirn.domains.connectors.observability.opentelemetry_config.OpenTelemetryConfig`.
"""

from __future__ import annotations

import unittest

from pirn.domains.connectors.observability.opentelemetry_config import OpenTelemetryConfig


class TestOpenTelemetryConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = OpenTelemetryConfig()
        self.assertIsNone(cfg.service_name)
        self.assertIsNone(cfg.endpoint)
        self.assertIsNone(cfg.headers)

    def test_construct_with_fields(self) -> None:
        cfg = OpenTelemetryConfig(
            service_name="my-service",
            endpoint="http://otel-collector:4317",
            headers={"Authorization": "Bearer my-token"},
        )
        self.assertEqual(cfg.service_name, "my-service")
        self.assertEqual(cfg.endpoint, "http://otel-collector:4317")
        self.assertEqual(cfg.headers, {"Authorization": "Bearer my-token"})

    def test_no_sensitive_fields(self) -> None:
        self.assertEqual(OpenTelemetryConfig.sensitive_fields, ())

    def test_frozen(self) -> None:
        cfg = OpenTelemetryConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.service_name = "mutated"  # type: ignore[misc]

    def test_audit_dict_class_marker(self) -> None:
        cfg = OpenTelemetryConfig(service_name="svc")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["_class"], "OpenTelemetryConfig")
        self.assertEqual(audit["service_name"], "svc")
