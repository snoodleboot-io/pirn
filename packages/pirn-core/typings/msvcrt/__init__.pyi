# Local type stub for the stdlib ``msvcrt`` module, declaring the byte-range
# locking subset ``pirn.core.transport.advisory_file_lock.AdvisoryFileLock`` uses
# on Windows.
#
# typeshed does ship msvcrt, but every symbol is gated behind
# ``sys.platform == "win32"``, so a checker running on Linux or macOS — which is
# every developer machine and every CI runner here — sees the module as empty and
# reports each attribute as missing. This stub declares the four names
# unconditionally so the Windows branch is type-checked everywhere instead of
# being suppressed (PIR-873).

LK_LOCK: int
LK_NBLCK: int
LK_NBRLCK: int
LK_RLCK: int
LK_UNLCK: int

def locking(fd: int, mode: int, nbytes: int) -> None: ...
