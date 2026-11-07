"""Root-only atomic broker HMAC key rotation.

Old grants are intentionally invalidated immediately; never rotate during
an in-flight job. Operators must quiesce broker before rotation.
"""
import os
import stat
from .signed_broker_service import read_broker_key


def rotate_broker_key(path, trusted_uid, trusted_gid):
    if os.geteuid() != 0:
        raise PermissionError("Root-only rotation")
    read_broker_key(path, trusted_uid, trusted_gid)
    tmp = path + ".new"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, 0, trusted_gid)
        os.fchmod(fd, 0o640)
        data = os.urandom(64)
        if os.write(fd, data) != len(data):
            raise OSError("Short key write")
        os.fsync(fd)
        os.replace(tmp, path)
        directory = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.close(fd)
        if os.path.lexists(tmp):
            os.unlink(tmp)
    return True
