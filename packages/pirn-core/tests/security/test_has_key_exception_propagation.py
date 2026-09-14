"""Security tests: M-1 — S3 and GCS ``has()`` propagates non-404 exceptions.

A presence check that swallowed an ``AccessDenied`` would report "not
cached" and silently recompute against a store it cannot actually reach;
only a genuine not-found may become ``False``.
"""

from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock


class _NoSuchKeyError(Exception):
    pass


class _AccessDeniedError(Exception):
    pass


class _AuthError(Exception):
    pass


def _s3_session(head_object: Any) -> MagicMock:
    """A session whose one client answers ``head_object`` with ``head_object``."""
    client = AsyncMock()
    client.head_object = head_object
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.client = MagicMock(return_value=ctx)
    return session


class TestS3HasKeyExceptionPropagation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ["PIRN_ENV"] = "test"
        from pirn.backends.signer import Signer

        self._signer = Signer.test_signer()

    def tearDown(self) -> None:
        os.environ.pop("PIRN_ENV", None)

    async def test_not_found_returns_false(self) -> None:
        from pirn.backends.s3_data_store import S3DataStore

        session = _s3_session(AsyncMock(side_effect=_NoSuchKeyError("NoSuchKey")))
        store = S3DataStore(bucket="test", session=session, signer=self._signer)

        assert await store.has("sha256:some-key") is False

    async def test_access_denied_propagates(self) -> None:
        from pirn.backends.s3_data_store import S3DataStore

        session = _s3_session(AsyncMock(side_effect=_AccessDeniedError("AccessDenied")))
        store = S3DataStore(bucket="test", session=session, signer=self._signer)

        with self.assertRaises(_AccessDeniedError):
            await store.has("sha256:some-key")


class TestGCSHasKeyExceptionPropagation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ["PIRN_ENV"] = "test"
        from pirn.backends.signer import Signer

        self._signer = Signer.test_signer()

    def tearDown(self) -> None:
        os.environ.pop("PIRN_ENV", None)

    async def test_404_returns_false(self) -> None:
        from pirn.backends.gcs_data_store import GCSDataStore

        storage = AsyncMock()
        storage.download_metadata = AsyncMock(side_effect=Exception("404 Not Found"))
        store = GCSDataStore(bucket="test", client=storage, signer=self._signer)

        assert await store.has("sha256:some-key") is False

    async def test_auth_error_propagates(self) -> None:
        from pirn.backends.gcs_data_store import GCSDataStore

        storage = AsyncMock()
        storage.download_metadata = AsyncMock(side_effect=_AuthError("credentials"))
        store = GCSDataStore(bucket="test", client=storage, signer=self._signer)

        with self.assertRaises(_AuthError):
            await store.has("sha256:some-key")
