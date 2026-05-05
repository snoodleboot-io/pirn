"""Security tests: M-3 + L-2 — _Signer key length enforcement and test_signer guard."""

from __future__ import annotations

import base64
import os
import unittest


class TestFromEnvMinimumKeyLength(unittest.TestCase):
    def setUp(self) -> None:
        self._var = "PIRN_TEST_SIGNING_KEY_SEC"
        os.environ.pop(self._var, None)

    def tearDown(self) -> None:
        os.environ.pop(self._var, None)

    def test_32_byte_key_accepted(self) -> None:
        from pirn.backends._signer import _Signer
        key = base64.b64encode(b"a" * 32).decode()
        os.environ[self._var] = key
        signer = _Signer.from_env(self._var)
        assert signer is not None

    def test_31_byte_key_rejected(self) -> None:
        from pirn.backends._signer import _Signer
        key = base64.b64encode(b"a" * 31).decode()
        os.environ[self._var] = key
        with self.assertRaises(ValueError) as ctx:
            _Signer.from_env(self._var)
        assert "31 bytes" in str(ctx.exception)

    def test_1_byte_key_rejected(self) -> None:
        from pirn.backends._signer import _Signer
        key = base64.b64encode(b"x").decode()
        os.environ[self._var] = key
        with self.assertRaises(ValueError) as ctx:
            _Signer.from_env(self._var)
        assert "32 bytes" in str(ctx.exception)

    def test_missing_env_var_raises(self) -> None:
        from pirn.backends._signer import _Signer
        with self.assertRaises(ValueError):
            _Signer.from_env(self._var)


class TestTestSignerProductionGuard(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("PIRN_ENV", None)

    def test_test_signer_allowed_in_test_env(self) -> None:
        from pirn.backends._signer import _Signer
        os.environ["PIRN_ENV"] = "test"
        signer = _Signer.test_signer()
        assert signer is not None

    def test_test_signer_allowed_in_ci_env(self) -> None:
        from pirn.backends._signer import _Signer
        os.environ["PIRN_ENV"] = "ci"
        signer = _Signer.test_signer()
        assert signer is not None

    def test_test_signer_blocked_in_production(self) -> None:
        from pirn.backends._signer import _Signer
        os.environ["PIRN_ENV"] = "production"
        with self.assertRaises(RuntimeError) as ctx:
            _Signer.test_signer()
        assert "production" in str(ctx.exception)

    def test_test_signer_blocked_when_env_unset(self) -> None:
        from pirn.backends._signer import _Signer
        os.environ.pop("PIRN_ENV", None)
        with self.assertRaises(RuntimeError):
            _Signer.test_signer()
