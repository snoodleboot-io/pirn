"""Complementary _Signer tests (signing path covered in test_data_store_signing.py).

These tests focus on edge cases not covered by the existing signing tests:
key material strength, test_signer helper, multiple keys produce different signatures.
"""

from __future__ import annotations

import base64
import os
import unittest
import unittest.mock

from pirn.backends._signer import _Signer


class TestSignerKeyIsolation(unittest.TestCase):
    """Different keys produce different, non-cross-verifiable signatures."""

    def test_different_keys_produce_different_signatures(self) -> None:
        s1 = _Signer(b"key-one-32-bytes-padding-aaaaaaa")
        s2 = _Signer(b"key-two-32-bytes-padding-bbbbbbb")
        payload = b"test payload"
        self.assertNotEqual(s1.sign(payload), s2.sign(payload))

    def test_cross_key_verify_raises(self) -> None:
        s1 = _Signer(b"key-one-32-bytes-padding-aaaaaaa")
        s2 = _Signer(b"key-two-32-bytes-padding-bbbbbbb")
        signed = s1.sign(b"data")
        with self.assertRaises(ValueError):
            s2.verify(signed)

    def test_signed_payload_longer_than_original(self) -> None:
        signer = _Signer(b"key-32-bytes-padding-xxxxxxxxxxx")
        payload = b"hello"
        signed = signer.sign(payload)
        # HMAC-SHA256 adds 32 bytes
        self.assertEqual(len(signed), len(payload) + 32)


class TestSignerTestHelper(unittest.TestCase):
    def test_test_signer_is_deterministic(self) -> None:
        s1 = _Signer.test_signer()
        s2 = _Signer.test_signer()
        payload = b"deterministic"
        self.assertEqual(s1.sign(payload), s2.sign(payload))

    def test_test_signer_verify_succeeds(self) -> None:
        s = _Signer.test_signer()
        payload = b"check"
        self.assertEqual(s.verify(s.sign(payload)), payload)


class TestSignerFromEnv(unittest.TestCase):
    def test_from_env_accepts_valid_base64_key(self) -> None:
        key = os.urandom(32)
        key_b64 = base64.b64encode(key).decode()
        with unittest.mock.patch.dict(os.environ, {"PIRN_SIGNING_KEY": key_b64}):
            signer = _Signer.from_env()
        # Can sign and verify without error
        data = b"env test"
        self.assertEqual(signer.verify(signer.sign(data)), data)

    def test_from_env_uses_custom_var_name(self) -> None:
        key = os.urandom(32)
        key_b64 = base64.b64encode(key).decode()
        with unittest.mock.patch.dict(os.environ, {"MY_KEY": key_b64}):
            signer = _Signer.from_env("MY_KEY")
        self.assertIsNotNone(signer)


class TestSignerVerifyEdgeCases(unittest.TestCase):
    def test_verify_exactly_32_bytes_raises_too_short(self) -> None:
        # Exactly 32 bytes = valid MAC prefix but empty payload
        signer = _Signer.test_signer()
        payload = b"x" * 32
        # Not a valid signature, so should raise mismatch
        with self.assertRaises(ValueError):
            signer.verify(payload)

    def test_verify_empty_bytes_raises_too_short(self) -> None:
        signer = _Signer.test_signer()
        with self.assertRaisesRegex(ValueError, "too short"):
            signer.verify(b"")

    def test_verify_returns_exact_original_bytes(self) -> None:
        signer = _Signer.test_signer()
        original = b"\x00\x01\x02\xFF" * 100
        self.assertEqual(signer.verify(signer.sign(original)), original)
