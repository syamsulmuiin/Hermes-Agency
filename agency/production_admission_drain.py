"""Root-only exclusive admission drain lease for authorized cutover controllers.

Keep the returned context open through handover AND rollback. Closing it
reopens admission. This does not stop brokers or modify systemd.
"""
import contextlib
import fcntl
import os
import pwd
import stat
import time

LOCK = "/run/hermes-operator/admission.lock"


@contextlib.contextmanager
def exclusive_admission_drain(*, timeout=30):
    if os.geteuid() != 0:
        raise PermissionError("Root required")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
        raise ValueError("Invalid drain timeout")
    fd = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid not in (0, pwd.getpwnam('hermes-trusted').pw_uid)
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise PermissionError("Unsafe admission lock")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Admission drain did not complete")
                time.sleep(0.05)
        try:
            print("OPERATOR_ADMISSION_DRAIN=LOCKED", flush=True)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
