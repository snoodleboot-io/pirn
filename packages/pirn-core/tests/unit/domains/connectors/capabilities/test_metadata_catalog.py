"""Tests for :class:`MetadataCatalog`."""

from __future__ import annotations

import unittest

from pirn.connectors.capabilities.metadata_catalog import MetadataCatalog


class TestMetadataCatalogInterface(unittest.IsolatedAsyncioTestCase):
    async def test_list_entities_raises_not_implemented(self) -> None:
        catalog = MetadataCatalog()
        with self.assertRaises(NotImplementedError):
            await catalog.list_entities("dataset")

    async def test_describe_entity_raises_not_implemented(self) -> None:
        catalog = MetadataCatalog()
        with self.assertRaises(NotImplementedError):
            await catalog.describe_entity("urn:li:dataset:123")
