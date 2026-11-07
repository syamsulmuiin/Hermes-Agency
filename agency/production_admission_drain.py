"""Root-only exclusive admission drain lease for authorized cutover controllers.

Keep the returned context open through handover AND rollback. Closing it
reopens admission. This does not stop brokers or modify systemd.
"""
import contextlib
import fcntl
import os
import stat
import time

LOCK = "/run/hermes-admission/admission.lock"


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
                or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) != 0o640):
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
            current = os.stat(LOCK, follow_symlinks=False)
            if (current.st_dev != info.st_dev or current.st_ino != info.st_ino
                    or current.st_nlink != 1):
                raise PermissionError("Admission lock inode changed")
            print("OPERATOR_ADMISSION_DRAIN=LOCKED", flush=True)
            yield
            # Verify the lock pathname still references the held inode before\n            # releasing the exclusive lease; fail closed on replacement.\n            current = os.stat(LOCK, follow_symlinks=False)\n            if (current.st_dev != info.st_dev or current.st_ino != info.st_ino\n                    or current.st_nlink != 1):\n                raise PermissionError("Admission lock inode changed during drain")\n        finally:\n            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
