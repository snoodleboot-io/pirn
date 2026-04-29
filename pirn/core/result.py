"""Result type alias.

Ok, Err, Skipped live in their own files; this module provides the
``Result`` union type for type annotations.
"""

from __future__ import annotations

from typing import TypeVar

from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped

T = TypeVar("T")

Result = Ok[T] | Err | Skipped

__all__ = ["Ok", "Err", "Skipped", "Result"]
