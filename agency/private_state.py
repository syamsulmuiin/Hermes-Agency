"""Validate deployment permissions for trusted SQLite and credential secrets.

Checks only; never creates files, changes permissions or assumes a sandbox.
The trusted service must run as a distinct unprivileged OS identity.
"""
import os
import stat


def verify_private_state(directory, database_path, key_directory):
    """Fail closed unless trusted state is owned by the current service UID."""
    uid = os.geteuid()
    root = os.path.abspath(os.fspath(directory))
    database = os.path.abspath(os.fspath(database_path))
    keys = os.path.abspath(os.fspath(key_directory))
    if (keys == root or database == root
        or not keys.startswith(root + os.sep)
        or not database.startswith(root + os.sep)
        or database.startswith(keys + os.sep)):
        raise PermissionError("Invalid trusted state layout")
    for path in (root, keys):
        entry = os.lstat(path)
        if (not stat.S_ISDIR(entry.st_mode) or entry.st_uid != uid
            or stat.S_IMODE(entry.st_mode) != 0o700):
            raise PermissionError("Trusted directory must be owner-only")
    entry = os.lstat(database)
    if (not stat.S_ISREG(entry.st_mode) or entry.st_uid != uid
        or stat.S_IMODE(entry.st_mode) != 0o600):
        raise PermissionError("Trusted database must be owner-only")
    for suffix in ("-wal", "-shm", "-journal"):
        candidate = database + suffix
        if os.path.lexists(candidate):
            entry = os.lstat(candidate)
            if (not stat.S_ISREG(entry.st_mode) or entry.st_uid != uid
                or stat.S_IMODE(entry.st_mode) != 0o600):
                raise PermissionError("Trusted SQLite auxiliary file unsafe")
    return True
