"""Tests for :class:`pirn.connectors.messaging.telegram_config.TelegramConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.messaging.telegram_config import TelegramConfig


class TestTelegramConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = TelegramConfig()
        self.assertEqual(cfg.bot_token, "")
        self.assertIsNone(cfg.default_chat_id)
        self.assertEqual(cfg.parse_mode, "HTML")
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_valid_parse_mode_markdown(self) -> None:
        cfg = TelegramConfig(bot_token="123:ABC", parse_mode="Markdown")
        self.assertEqual(cfg.parse_mode, "Markdown")

    def test_construct_with_valid_parse_mode_markdownv2(self) -> None:
        cfg = TelegramConfig(parse_mode="MarkdownV2")
        self.assertEqual(cfg.parse_mode, "MarkdownV2")

    def test_invalid_parse_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            TelegramConfig(parse_mode="INVALID")

    def test_sensitive_fields(self) -> None:
        self.assertIn("bot_token", TelegramConfig.sensitive_fields)

    def test_repr_redacts_bot_token(self) -> None:
        cfg = TelegramConfig(bot_token="123:super-secret")
        text = repr(cfg)
        self.assertNotIn("super-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = TelegramConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.parse_mode = "Markdown"  # type: ignore[misc]

    def test_numeric_chat_id(self) -> None:
        cfg = TelegramConfig(default_chat_id=-1001234567890)
        self.assertEqual(cfg.default_chat_id, -1001234567890)
