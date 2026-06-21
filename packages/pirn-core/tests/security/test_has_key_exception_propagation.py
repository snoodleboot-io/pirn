"""Security tests: M-1 — S3 and GCS _has_key propagates non-404 exceptions."""

from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock


class TestS3HasKeyExceptionPropagation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ["PIRN_ENV"] = "test"
        from pirn.backends._signer import _Signer
        self._signer = _Signer.test_signer()

    def tearDown(self) -> None:
        os.environ.pop("PIRN_ENV", None)

    async def test_not_found_returns_false(self) -> None:
        from pirn.backends.s3 import S3DataStore

        class _NoSuchKeyError(Exception):
            pass

        mock_s3 = AsyncMock()
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=False)
        mock_s3.head_object = AsyncMock(side_effect=_NoSuchKeyError("NoSuchKey"))

        session = MagicMock()
        session.client = MagicMock(return_value=mock_s3)
        mock_session = AsyncMock(return_value=session)

        store = S3DataStore(bucket="test", session=session, signer=self._signer)
        store._S3DataStore__client = mock_session  # type: ignore[attr-defined]
        store._S3DataStore__s3 = lambda s: mock_s3  # type: ignore[attr-defined]

        result = await store._has_key("some/key")
        assert result is False

    async def test_access_denied_propagates(self) -> None:
        from pirn.backends.s3 import S3DataStore

        class _AccessDeniedError(Exception):
            pass

        mock_s3 = AsyncMock()
        mock_s3.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_s3.__aexit__ = AsyncMock(return_value=False)
        mock_s3.head_object = AsyncMock(side_effect=_AccessDeniedError("AccessDenied"))

        session = MagicMock()
        store = S3DataStore(bucket="test", session=session, signer=self._signer)
        store._S3DataStore__client = AsyncMock(return_value=session)  # type: ignore[attr-defined]
        store._S3DataStore__s3 = lambda s: mock_s3  # type: ignore[attr-defined]

        with self.assertRaises(_AccessDeniedError):
            await store._has_key("some/key")


class TestGCSHasKeyExceptionPropagation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ["PIRN_ENV"] = "test"
        from pirn.backends._signer import _Signer
        self._signer = _Signer.test_signer()

    def tearDown(self) -> None:
        os.environ.pop("PIRN_ENV", None)

    async def test_404_returns_false(self) -> None:
        from pirn.backends.gcs import GCSDataStore

        mock_storage = AsyncMock()
        mock_storage.__aenter__ = AsyncMock(return_value=mock_storage)
        mock_storage.__aexit__ = AsyncMock(return_value=False)
        mock_storage.download_metadata = AsyncMock(side_effect=Exception("404 Not Found"))

        store = GCSDataStore(bucket="test", signer=self._signer)
        store._GCSDataStore__storage = lambda: mock_storage  # type: ignore[attr-defined]

        result = await store._has_key("some/key")
        assert result is False

    async def test_auth_error_propagates(self) -> None:
        from pirn.backends.gcs import GCSDataStore

        class _AuthError(Exception):
            pass

        mock_storage = AsyncMock()
        mock_storage.__aenter__ = AsyncMock(return_value=mock_storage)
        mock_storage.__aexit__ = AsyncMock(return_value=False)
        mock_storage.download_metadata = AsyncMock(side_effect=_AuthError("credentials"))

        store = GCSDataStore(bucket="test", signer=self._signer)
        store._GCSDataStore__storage = lambda: mock_storage  # type: ignore[attr-defined]

        with self.assertRaises(_AuthError):
            await store._has_key("some/key")
