"""Cross-platform advisory file locking for the harness runtime substrate.

The substrate serializes read-modify-write cycles on shared JSON and appends to
JSONL logs by holding an EXCLUSIVE lock on an open file handle. POSIX provides
this via ``fcntl.flock``; Windows provides an equivalent via ``msvcrt.locking``.
This module exposes one interface -- ``lock_ex(fh)`` / ``unlock(fh)`` -- backed
by whichever primitive exists on the running platform, so the rest of the
substrate stays platform-agnostic and stdlib-only (no PyPI ``portalocker``).

Semantics contract (must hold identically on every platform):
  - ``lock_ex(fh)`` blocks until it holds an exclusive lock covering the file,
    then returns. Concurrent holders in other processes wait.
  - ``unlock(fh)`` releases a lock previously taken on the same handle.
  - Locks are advisory and released when the handle is closed.

Implementation notes:
  - ``fcntl.flock`` takes a whole-file advisory lock. ``msvcrt.locking`` locks a
    byte *range*, so every caller must lock the SAME single byte (offset 0). That
    byte then behaves as a global mutex for the file, regardless of where data is
    written (append writes still land at EOF). Byte 0 need not exist yet --
    Windows permits locking a region at or past end-of-file.
  - ``msvcrt.locking(LK_LOCK)`` is not truly blocking: it retries ~10 times at 1s
    intervals, then raises ``OSError``. We wrap it in a retry loop so the call
    blocks until the lock is ours -- the same guarantee ``fcntl.LOCK_EX`` gives.
    Each internal attempt sleeps, so the loop waits rather than busy-spinning.
"""
import os

if os.name == "nt":  # Windows
    import msvcrt

    _LOCK_BYTES = 1

    def lock_ex(fh):
        fh.seek(0)
        while True:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, _LOCK_BYTES)
                return
            except OSError:
                # LK_LOCK already blocked ~10s across its internal retries
                # before raising; keep waiting so we match fcntl's
                # block-until-acquired contract instead of giving up.
                continue

    def unlock(fh):
        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, _LOCK_BYTES)
        except OSError:
            # Unlocking a byte we do not hold is a no-op for our purposes; the
            # lock is released on close regardless.
            pass

else:  # POSIX: Linux, macOS, *BSD

    import fcntl

    def lock_ex(fh):
        fcntl.flock(fh, fcntl.LOCK_EX)

    def unlock(fh):
        fcntl.flock(fh, fcntl.LOCK_UN)
