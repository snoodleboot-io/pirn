"""Tests for :class:`pirn.connectors.dsn_scrubber.DsnScrubber`."""

from __future__ import annotations

import unittest

from pirn.connectors.dsn_scrubber import DsnScrubber


class TestDsnScrubber(unittest.TestCase):
    def test_redacts_inline_password_in_dsn(self) -> None:
        scrubber = DsnScrubber()
        out = scrubber.scrub("postgres://alice:s3cret@db.example.com:5432/main")
        assert "s3cret" not in out
        assert out == "postgres://<redacted>@db.example.com:5432/main"

    def test_redacts_password_in_postgresql_scheme(self) -> None:
        scrubber = DsnScrubber()
        out = scrubber.scrub("postgresql+asyncpg://u:p@host/db")
        assert "p@" not in out
        assert "<redacted>" in out

    def test_redacts_token_query_string(self) -> None:
        scrubber = DsnScrubber()
        out = scrubber.scrub("https://api.example.com/v1/x?api_key=AKIA1234&other=ok")
        assert "AKIA1234" not in out
        assert "other=ok" in out

    def test_redacts_signature_param(self) -> None:
        scrubber = DsnScrubber()
        out = scrubber.scrub(
            "https://s3.example.com/bucket/key?signature=abcdef&expires=99"
        )
        assert "abcdef" not in out

    def test_idempotent_on_already_redacted_dsn(self) -> None:
        scrubber = DsnScrubber()
        once = scrubber.scrub("postgres://u:p@host/db")
        twice = scrubber.scrub(once)
        assert once == twice

    def test_passes_through_non_dsn_strings(self) -> None:
        scrubber = DsnScrubber()
        assert scrubber.scrub("just some text") == "just some text"
        assert scrubber.scrub("") == ""
