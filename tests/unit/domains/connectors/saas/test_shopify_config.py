"""Tests for :class:`pirn.domains.connectors.saas.shopify_config.ShopifyConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.saas.shopify_config import ShopifyConfig


class TestShopifyConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = ShopifyConfig()
        self.assertIsNone(cfg.shop_url)
        self.assertIsNone(cfg.access_token)
        self.assertEqual(cfg.api_version, "2024-04")

    def test_construct_with_fields(self) -> None:
        cfg = ShopifyConfig(
            shop_url="my-store.myshopify.com",
            access_token="shpat_secret",
            api_version="2024-07",
        )
        self.assertEqual(cfg.shop_url, "my-store.myshopify.com")
        self.assertEqual(cfg.api_version, "2024-07")

    def test_sensitive_fields(self) -> None:
        self.assertIn("access_token", ShopifyConfig.sensitive_fields)

    def test_repr_redacts_access_token(self) -> None:
        cfg = ShopifyConfig(access_token="shpat-secret")
        text = repr(cfg)
        self.assertNotIn("shpat-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = ShopifyConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.shop_url = "mutated"  # type: ignore[misc]
