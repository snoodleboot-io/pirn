from __future__ import annotations

import unittest

from pirn.managers.redact import redact_common_secrets


class TestRedactCommonSecrets(unittest.TestCase):
    def test_dsn_credentials_redacted(self):
        text = "postgresql://user:s3cr3t@db.host/mydb"
        result = redact_common_secrets(text)
        self.assertNotIn("s3cr3t", result)
        self.assertIn("<redacted>", result)
        self.assertIn("db.host", result)

    def test_password_assignment_redacted(self):
        text = "password=supersecret"
        result = redact_common_secrets(text)
        self.assertNotIn("supersecret", result)
        self.assertIn("<redacted>", result)

    def test_api_key_redacted(self):
        result = redact_common_secrets("api_key=abc123xyz")
        self.assertNotIn("abc123xyz", result)

    def test_token_redacted(self):
        result = redact_common_secrets("token=mytoken99")
        self.assertNotIn("mytoken99", result)

    def test_auth_header_redacted(self):
        text = "Authorization: Bearer eyJhbGc.payload.sig"
        result = redact_common_secrets(text)
        self.assertNotIn("eyJhbGc", result)
        self.assertIn("<redacted>", result)

    def test_unrelated_text_unchanged(self):
        text = "This is a normal log line with no secrets."
        result = redact_common_secrets(text)
        self.assertEqual(result, text)

    def test_empty_string(self):
        self.assertEqual(redact_common_secrets(""), "")

    def test_case_insensitive_password(self):
        result = redact_common_secrets("PASSWORD=abc")
        self.assertNotIn("abc", result)
