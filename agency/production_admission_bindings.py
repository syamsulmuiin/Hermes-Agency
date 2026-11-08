"""Production admission-lock bindings shared with operator_admission_lease.

No CLI, service operations, journal provisioning or cutover authorization.
"""
from contextlib import contextmanager
import fcntl
import os
import stat

from .production_maintenance_adapter import MaintenanceDenied


def _identity(fd, path):
    info = os.fstat(fd)
    current = os.stat(path, follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o640 or info.st_nlink != 1
            or not stat.S_ISREG(current.st_mode)
            or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)
            or current.st_nlink != 1):
        raise MaintenanceDenied("Unsafe or replaced admission lock")
    return info.st_dev, info.st_ino


class ProductionAdmissionBindings:
    """Exclusive counterpart to the existing shared operator admission lease."""

    def __init__(self):
        self._fd = None
        self._path = None

    @contextmanager
    def exclusive_drain(self, resolved):
        if self._fd is not None:
            raise MaintenanceDenied("Nested admission drain")
        path = resolved["paths"]["admission_lock"]
        if not os.path.isabs(path) or not hasattr(os, "O_NOFOLLOW"):
            raise MaintenanceDenied("Unsafe admission lock path")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            _identity(fd, path)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MaintenanceDenied("Admission drain is busy") from exc
            try:
                _identity(fd, path)
                self._fd, self._path = fd, path
                try:
                    yield
                finally:
                    _identity(fd, path)
            finally:
                self._fd, self._path = None, None
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def lock_identity(self, resolved):
        if self._fd is None or self._path != resolved["paths"]["admission_lock"]:
            raise MaintenanceDenied("Exclusive drain not held")
        return _identity(self._fd, self._path)
