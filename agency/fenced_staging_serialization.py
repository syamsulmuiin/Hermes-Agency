"""Staging-only serialization of fenced journal recovery and launches.

This module does not enable production execution. All callers using the same
journal MUST acquire this lock before recovery, gate checking, registration,
and launch. A separate independent watchdog is still required.
"""
import contextlib
import fcntl
import os
import stat

from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import register_before_launch, recover_owned_units, _verify_store


@contextlib.contextmanager
def staging_journal_lock(journal):
    """Root-only, non-symlink lock in the private journal directory."""
    if os.geteuid() != 0:
        raise PermissionError("Root broker required")
    _verify_store(journal)
    if not os.path.isfile(journal):
        raise PermissionError("Existing ownership journal required")
    directory = os.path.dirname(os.path.abspath(journal))
    lock_name = os.path.basename(journal) + ".launch.lock"
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(lock_name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                    or info.st_mode & 0o077 or info.st_nlink != 1):
                raise PermissionError("Unsafe launch lock")
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)


def staging_recover(journal, *, stop_unit=None):
    """Recover pending units while excluding cooperating launches."""
    with staging_journal_lock(journal):
        if stop_unit is None:
            return recover_owned_units(journal)
        return recover_owned_units(journal, stop_unit=stop_unit)


def staging_launch(journal, unit, launch):
    """Gate and durably register before invoking an operator-supplied runner.

    A launch failure deliberately leaves the record pending. This is not a
    complete broker: watchdog, signed-grant admission, and stop verification
    must be composed before using it for real execution.
    """
    if not callable(launch):
        raise TypeError("Launch callback required")
    with staging_journal_lock(journal):
        require_recovered(journal)
        register_before_launch(journal, unit)
        return launch()
