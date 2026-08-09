"""PIR-790: the import paths the trigger/streaming docs hand to users must work.

``pirn/triggers/__init__.py`` and ``pirn/streaming/__init__.py`` intentionally
export nothing — PIR-744 stripped the package façades because the house
convention forbids import forwarding, and
``scripts/check_no_import_forwarding.py`` enforces that workspace-wide.

The docs, however, still told users to write ``from pirn.triggers import
run_forever``, which raises ``ImportError``.  These tests pin the *concrete*
paths the docs now hand out, so a future doc edit that reintroduces a façade
import is caught, and so the deliberate absence of re-exports stays deliberate
rather than drifting back.
"""

from __future__ import annotations

import importlib
import unittest


class TestDocumentedConcreteImports(unittest.TestCase):
    """Every import path published in the docs resolves."""

    def test_documented_trigger_paths_resolve(self) -> None:
        for module_name, symbol in (
            ("pirn.triggers.base", "Trigger"),
            ("pirn.triggers.base", "run_forever"),
            ("pirn.triggers.cron", "CronTrigger"),
            ("pirn.triggers.http", "WebhookTrigger"),
            ("pirn.triggers.kafka", "KafkaTrigger"),
            ("pirn.triggers.valkey", "ValKeyTrigger"),
        ):
            with self.subTest(module=module_name, symbol=symbol):
                module = importlib.import_module(module_name)
                self.assertTrue(hasattr(module, symbol))

    def test_documented_streaming_paths_resolve(self) -> None:
        for module_name, symbol in (
            ("pirn.streaming.base", "StreamingSource"),
            ("pirn.streaming.base", "run_stream"),
            ("pirn.streaming.iterable", "IterableSource"),
            ("pirn.streaming.kafka", "KafkaStreamingSource"),
            ("pirn.streaming.file_tail", "FileTailSource"),
            ("pirn.streaming.trigger_adapter", "StreamingSourceTrigger"),
        ):
            with self.subTest(module=module_name, symbol=symbol):
                module = importlib.import_module(module_name)
                self.assertTrue(hasattr(module, symbol))


class TestPackagesExposeNoFacade(unittest.TestCase):
    """The empty ``__init__`` façades stay empty — no import forwarding."""

    def test_trigger_package_forwards_nothing(self) -> None:
        package = importlib.import_module("pirn.triggers")
        for symbol in ("Trigger", "run_forever", "CronTrigger", "WebhookTrigger"):
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(package, symbol))

    def test_streaming_package_forwards_nothing(self) -> None:
        package = importlib.import_module("pirn.streaming")
        for symbol in ("StreamingSource", "run_stream", "IterableSource"):
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(package, symbol))


class TestTapestryHasNoRunStream(unittest.TestCase):
    """``run_stream`` is a free function; the docs must not promise a method."""

    def test_tapestry_does_not_define_run_stream(self) -> None:
        tapestry_module = importlib.import_module("pirn.tapestry")
        self.assertFalse(hasattr(tapestry_module.Tapestry, "run_stream"))
