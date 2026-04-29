from __future__ import annotations

import base64
import os


def signing_key_from_env(var: str = "PIRN_SIGNING_KEY") -> bytes:
    """Read a base64-encoded signing key from an environment variable.

    Raises ``ValueError`` with a clear message if the variable is unset or empty.

    Example::

        import secrets, base64
        key_b64 = base64.b64encode(secrets.token_bytes(32)).decode()
        # Set PIRN_SIGNING_KEY=<key_b64> in your environment, then:
        store = LocalDiskDataStore("/data", signing_key=signing_key_from_env())
    """
    raw = os.environ.get(var)
    if not raw:
        raise ValueError(
            f"Environment variable {var!r} is not set or empty. "
            "Set it to a base64-encoded signing key before constructing a signed DataStore."
        )
    return base64.b64decode(raw)
