"""``KeyIndexUnreadableError`` — the key-index record could not be read (PIR-720).

Raised by ``MemoryStoreKeyIndex`` (deleted PIR-864, along with its one
consumer ``PersistedSessionStore``) when the backend cannot return the record
the key list lives in: a torn payload
left by a half-finished write, a rejected signature, a backend that is down.

It is a distinct type rather than the backend's own error because the correct
response is specific and not deducible from a ``ValueError`` about HMACs. The
*indexed data* is intact — only the derived index is unreadable — so recovery is
to scrub the index record and rebuild it, not to treat the store as lost. A
caller that wants to automate that recovery needs something narrower to catch
than ``Exception``.
"""

from __future__ import annotations


class KeyIndexUnreadableError(RuntimeError):
    """The persisted key-index record exists but could not be read back."""
