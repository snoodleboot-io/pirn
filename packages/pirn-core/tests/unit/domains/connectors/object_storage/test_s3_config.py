"""Tests for :class:`pirn.connectors.object_storage.s3_config.S3Config`."""

from __future__ import annotations

import unittest

from pirn.connectors.object_storage.s3_config import S3Config


class TestS3Config(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = S3Config()
        self.assertEqual(cfg.bucket, "")
        self.assertEqual(cfg.region, "us-east-1")
        self.assertIsNone(cfg.endpoint_url)
        self.assertIsNone(cfg.access_key_id)
        self.assertIsNone(cfg.secret_access_key)
        self.assertIsNone(cfg.session_token)
        self.assertEqual(cfg.multipart_threshold, 8 * 1024 * 1024)
        self.assertEqual(cfg.chunk_size, 1 << 20)

    def test_construct_with_fields(self) -> None:
        cfg = S3Config(
            bucket="my-bucket",
            region="eu-west-1",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI",
        )
        self.assertEqual(cfg.bucket, "my-bucket")
        self.assertEqual(cfg.region, "eu-west-1")

    def test_construct_with_custom_endpoint(self) -> None:
        cfg = S3Config(bucket="b", endpoint_url="https://minio.example.com")
        self.assertEqual(cfg.endpoint_url, "https://minio.example.com")

    def test_sensitive_fields(self) -> None:
        self.assertIn("access_key_id", S3Config.sensitive_fields)
        self.assertIn("secret_access_key", S3Config.sensitive_fields)
        self.assertIn("session_token", S3Config.sensitive_fields)

    def test_repr_redacts_credentials(self) -> None:
        cfg = S3Config(access_key_id="AKIA", secret_access_key="xK9mP2wQrT", session_token="tok")
        text = repr(cfg)
        self.assertNotIn("xK9mP2wQrT", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = S3Config()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.bucket = "mutated"  # type: ignore[misc]
