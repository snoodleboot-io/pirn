"""Tests for :class:`pirn.domains.connectors.streaming.kinesis_config.KinesisConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.streaming.kinesis_config import KinesisConfig


class TestKinesisConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = KinesisConfig()
        self.assertIsNone(cfg.region)
        self.assertIsNone(cfg.endpoint_url)
        self.assertIsNone(cfg.access_key_id)
        self.assertIsNone(cfg.secret_access_key)
        self.assertIsNone(cfg.session_token)
        self.assertIsNone(cfg.stream_arn)

    def test_construct_with_fields(self) -> None:
        cfg = KinesisConfig(
            region="us-east-1",
            access_key_id="AKIA",
            secret_access_key="secret",
            stream_arn="arn:aws:kinesis:us-east-1:123456789012:stream/my-stream",
        )
        self.assertEqual(cfg.region, "us-east-1")
        self.assertEqual(cfg.stream_arn, "arn:aws:kinesis:us-east-1:123456789012:stream/my-stream")

    def test_sensitive_fields(self) -> None:
        self.assertIn("access_key_id", KinesisConfig.sensitive_fields)
        self.assertIn("secret_access_key", KinesisConfig.sensitive_fields)
        self.assertIn("session_token", KinesisConfig.sensitive_fields)

    def test_repr_redacts_credentials(self) -> None:
        cfg = KinesisConfig(access_key_id="AKIA", secret_access_key="xK9mP2wQrT", session_token="tok")
        text = repr(cfg)
        self.assertNotIn("xK9mP2wQrT", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = KinesisConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.region = "mutated"  # type: ignore[misc]
