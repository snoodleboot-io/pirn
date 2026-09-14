"""Stand-ins for the typed "not found" exceptions the cloud object-store SDKs raise.

The stores classify a missing object by the SDK's exception *type* (botocore
``ClientError`` with a not-found code, azure-core ``ResourceNotFoundError``,
aiohttp ``ClientResponseError`` with status 404), never by message text. The
SDKs are optional, so the tests install minimal modules of the same dotted
names into ``sys.modules`` for the duration of a test and build errors from
them.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any
from unittest import mock


class SdkErrors:
    """Install fake SDK exception modules and build typed errors from them."""

    @staticmethod
    def _client_error_init(self: Any, error_response: dict[str, Any], operation_name: str) -> None:
        Exception.__init__(self, f"An error occurred ({error_response['Error']['Code']})")
        self.response = error_response
        self.operation_name = operation_name

    @staticmethod
    def _response_error_init(self: Any, status: int, message: str = "") -> None:
        Exception.__init__(self, f"{status}, message={message!r}")
        self.status = status

    @classmethod
    @contextmanager
    def installed(cls) -> Iterator[None]:
        """Patch ``sys.modules`` with the three fake SDK exception modules."""
        botocore = ModuleType("botocore.exceptions")
        client_error = type("ClientError", (Exception,), {"__init__": cls._client_error_init})
        botocore.ClientError = client_error
        azure = ModuleType("azure.core.exceptions")
        http_response_error = type("HttpResponseError", (Exception,), {})
        azure.HttpResponseError = http_response_error
        azure.ResourceNotFoundError = type("ResourceNotFoundError", (http_response_error,), {})
        aiohttp = ModuleType("aiohttp")
        response_error = type(
            "ClientResponseError", (Exception,), {"__init__": cls._response_error_init}
        )
        aiohttp.ClientResponseError = response_error
        with mock.patch.dict(
            sys.modules,
            {"botocore.exceptions": botocore, "azure.core.exceptions": azure, "aiohttp": aiohttp},
        ):
            yield

    @staticmethod
    def s3(code: str) -> Exception:
        """A botocore ``ClientError`` carrying S3 error ``code`` (``NoSuchKey``, ``404``, ...)."""
        error_type: type[Exception] = sys.modules["botocore.exceptions"].ClientError
        return error_type({"Error": {"Code": code, "Message": "x"}}, "GetObject")

    @staticmethod
    def azure_not_found() -> Exception:
        """An azure-core ``ResourceNotFoundError`` (``BlobNotFound``)."""
        error_type: type[Exception] = sys.modules["azure.core.exceptions"].ResourceNotFoundError
        return error_type("The specified blob does not exist. ErrorCode:BlobNotFound")

    @staticmethod
    def azure_http(message: str) -> Exception:
        """An azure-core ``HttpResponseError`` that is not a not-found."""
        error_type: type[Exception] = sys.modules["azure.core.exceptions"].HttpResponseError
        return error_type(message)

    @staticmethod
    def gcs(status: int, message: str = "") -> Exception:
        """An aiohttp ``ClientResponseError`` with HTTP ``status``."""
        error_type: type[Exception] = sys.modules["aiohttp"].ClientResponseError
        return error_type(status, message)
