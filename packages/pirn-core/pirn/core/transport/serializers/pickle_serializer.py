"""``PickleSerializer`` — signed fallback serialiser using Python's pickle protocol.

Used for any value type not covered by a more specific serialiser. Pickle handles
arbitrary Python objects but produces non-portable bytes (Python version and class
path sensitive); register more specific serialisers (numpy, arrow, …) for types
that cross process or language boundaries.

.. note::
    ``pickle.loads`` on bytes an attacker can write is a remote-code-execution
    sink, and the transports that reach this serialiser read from S3, Valkey and
    the local filesystem — stores outside the pirn process. So the same policy
    :class:`~pirn.backends.base.cloud_object_store.CloudObjectStore` applies to
    ``cloudpickle`` applies here: construction refuses without a ``signer``
    unless the caller passes ``allow_unsigned=True`` *and* sets
    ``PIRN_ALLOW_UNSIGNED=1``, acknowledging that the store is inside the same
    trust boundary as this process (PIR-873). With a signer, every payload
    carries an HMAC-SHA256 tag that :meth:`deserialise` verifies before pickle
    sees a byte of it.
"""

from __future__ import annotations

import logging
import os
import pickle
from typing import TYPE_CHECKING, Any

from pirn.core.transport.serializers.serialiser_error import SerialiserError
from pirn.core.transport.serializers.serializer import Serializer
from pirn.exceptions.data_integrity_error import DataIntegrityError

if TYPE_CHECKING:
    from pirn.backends.signer import Signer

_log = logging.getLogger(__name__)


class PickleSerializer(Serializer):
    """Serialise any Python value via ``pickle`` (protocol 5), HMAC-signed."""

    def __init__(self, *, signer: Signer | None = None, allow_unsigned: bool = False) -> None:
        """Configure signing.

        Args:
            signer: The :class:`~pirn.backends.signer.Signer` whose HMAC tag is
                prepended on write and verified on read. Required in production.
            allow_unsigned: When ``True``, operate without signing. Also requires
                the ``PIRN_ALLOW_UNSIGNED=1`` environment variable. Only for
                single-tenant development or test environments.

        Raises:
            ValueError: If neither ``signer`` nor ``allow_unsigned=True`` is
                given, or ``allow_unsigned=True`` without ``PIRN_ALLOW_UNSIGNED=1``.
        """
        if signer is None and not allow_unsigned:
            raise ValueError(
                "PickleSerializer: refusing to construct an unsigned pickle "
                "serialiser. pickle.loads on attacker-controlled bytes is a "
                "remote-code-execution sink, and the transports that use this "
                "serialiser read from S3, Valkey and local disk. Pass a "
                "`signer=` (production) or `allow_unsigned=True` "
                "(single-tenant dev / test only) to acknowledge the "
                "trust-boundary assumption."
            )
        if signer is None:
            if os.environ.get("PIRN_ALLOW_UNSIGNED") != "1":
                raise ValueError(
                    "PickleSerializer: allow_unsigned=True requires the environment "
                    "variable PIRN_ALLOW_UNSIGNED=1 to be set. This prevents "
                    "accidental unsigned pickle in production. Set "
                    "PIRN_ALLOW_UNSIGNED=1 only in development or test environments."
                )
            _log.warning(
                "PickleSerializer constructed without HMAC signing (allow_unsigned=True). "
                "pickle.loads on attacker-controlled bytes is an RCE sink. Ensure the "
                "transport's backing store is within the same trust boundary as this process."
            )
        self._signer = signer

    @property
    def signed(self) -> bool:
        """Whether payloads carry an HMAC tag this serialiser verifies on read."""
        return self._signer is not None

    def serialise(self, value: Any) -> bytes:
        try:
            payload = pickle.dumps(value, protocol=5)
        except Exception as exc:
            raise SerialiserError(
                f"PickleSerializer: cannot serialise {type(value).__name__}: {exc}"
            ) from exc
        return payload if self._signer is None else self._signer.sign(payload)

    def deserialise(self, data: bytes, type_name: str) -> Any:
        """Verify the HMAC tag, then unpickle — in that order, never the reverse.

        Raises:
            DataIntegrityError: If the payload's signature does not verify. It
                propagates rather than becoming a ``SerialiserError``: a
                signature mismatch is not a malformed value, it is a payload
                this process must not deserialise.
            SerialiserError: If verified bytes cannot be unpickled.
        """
        payload = data
        if self._signer is not None:
            payload = self._signer.verify(data)
        try:
            return pickle.loads(payload)
        except DataIntegrityError:
            raise
        except Exception as exc:
            raise SerialiserError(
                f"PickleSerializer: cannot deserialise {type_name}: {exc}"
            ) from exc

    def can_handle(self, value: Any) -> bool:
        return True
