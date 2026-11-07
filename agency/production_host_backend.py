"""Host-facing maintenance backend with injected, isolated operations.

No production execution entrypoint. All mutations are delegated to an
explicitly supplied operations object; construction never changes the host.
The default is deny-all. This module cannot authorize a cutover.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat

from .production_maintenance_adapter import MaintenanceDenied


class DenyAllOperations:
    def __getattr__(self, name):
        raise MaintenanceDenied("Unreviewed host operation denied: " + name)


class IsolatedHostBackend:
    """Production-shaped host checks, injectable operations, no default writes.

    lock_path and freeze_path MUST be paths inside an isolated test root until
    independently reviewed production integration is authorized. The injected
    operations provider is responsible for service/socket/journal semantics.
    """

    def __init__(self, lock_path, freeze_path, operations=None):
        self.lock_path = Path(lock_path)
        self.freeze_path = Path(freeze_path)
        self.ops = operations if operations is not None else DenyAllOperations()
        self._lock_fd = None
        self._lock_stat = None

    def _regular(self, path, mode):
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != mode):
            raise MaintenanceDenied("Unsafe maintenance file: " + str(path))
        return info

    @contextmanager
    def exclusive_drain(self):
        if self._lock_fd is not None:
            raise MaintenanceDenied("Drain already held")
        info = self._regular(self.lock_path, 0o640)
        fd = os.open(self.lock_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            held = os.fstat(fd)
            if (held.st_dev, held.st_ino) != (info.st_dev, info.st_ino):
                raise MaintenanceDenied("Admission lock replaced during open")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd = fd
            self._lock_stat = (held.st_dev, held.st_ino)
            if self.lock_identity() != self._lock_stat:
                raise MaintenanceDenied("Admission lock replaced during drain")
            # A flock alone is NOT proof the live sidecar participates.
            if self.ops.admission_participation_verified() is not True:
                raise MaintenanceDenied("Live admission participation not proven")
            yield
        finally:
            self._lock_fd = None
            self._lock_stat = None
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def lock_identity(self):
        if self._lock_fd is None:
            raise MaintenanceDenied("Exclusive drain not held")
        info = self._regular(self.lock_path, 0o640)
        if (info.st_dev, info.st_ino) != self._lock_stat:
            raise MaintenanceDenied("Admission inode changed")
        return self._lock_stat

    def freeze_verified(self):
        try:
            self._regular(self.freeze_path, 0o600)
        except FileNotFoundError:
            return False
        return True

    def runtime_evidence(self):
        return self.ops.runtime_evidence()

    def freeze(self):
        self.ops.freeze()

    def quiesce(self):
        if self.ops.quiescence_verified() is not True:
            raise MaintenanceDenied("Quiescence not verified")

    def stop_old(self):
        self.ops.stop_old()
        if self.ops.legacy_stopped_verified() is not True:
            raise MaintenanceDenied("Legacy service still active")

    def replay_ledger_identity(self):
        return self.ops.replay_ledger_identity()

    def bootstrap_existing_journal(self):
        self.ops.bootstrap_existing_journal()
        if self.ops.journal_recovered_verified() is not True:
            raise MaintenanceDenied("Journal recovery unverified")

    def start_new(self):
        self.ops.start_new()
        if self.ops.fenced_started_verified() is not True:
            raise MaintenanceDenied("Fenced service start unverified")

    def route_new(self):
        self.ops.route_new()

    def route_verified(self, expected):
        return self.ops.route_verified(expected) is True

    def replay_denied(self):
        return self.ops.replay_denied() is True

    def health(self):
        if self.ops.health_verified() is not True:
            raise MaintenanceDenied("Host health not verified")

    def rollback_route_and_service(self):
        self.ops.rollback_route_and_service()

    def legacy_verified(self):
        return self.ops.legacy_verified() is True

    def unfreeze(self):
        self.ops.unfreeze()

    def quarantine(self):
        self.ops.quarantine()

    def quarantine_verified(self):
        return self.freeze_verified() and self.ops.quarantine_verified() is True
