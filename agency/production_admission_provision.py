"""Provision a stable root-owned admission lock without touching services.

Run before deploying the lock-aware sidecar. The directory is root-owned
0755, the lock is root:hermes-trusted 0640. Never unlink or replace a
pre-existing lock: an active flock may reference its inode.
"""
import argparse
import os
import pwd
import grp
import stat

DIRECTORY = "/run/hermes-admission"
LOCK = DIRECTORY + "/admission.lock"


def provision(directory=DIRECTORY, trusted_group="hermes-trusted"):
    if os.geteuid() != 0:
        raise PermissionError("Root required")
    group = grp.getgrnam(trusted_group).gr_gid
    if not os.path.lexists(directory):
        os.mkdir(directory, 0o755)
    parent = os.lstat(directory)
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
            or stat.S_IMODE(parent.st_mode) != 0o755):
        raise PermissionError("Unsafe admission directory")
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        lock_fd = os.open("admission.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL |
                          os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd) if not os.path.lexists(LOCK) else None
        if lock_fd is not None:
            try:
                os.fchown(lock_fd, 0, group)
                os.fchmod(lock_fd, 0o640)
                os.fsync(lock_fd)
            finally:
                os.close(lock_fd)
            os.fsync(fd)
        lock_fd = os.open("admission.lock", os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            info = os.fstat(lock_fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                    or info.st_gid != group or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o640):
                raise PermissionError("Unsafe admission lock")
            path_info = os.stat("admission.lock", dir_fd=fd, follow_symlinks=False)
            if (path_info.st_dev, path_info.st_ino) != (info.st_dev, info.st_ino):
                raise PermissionError("Admission lock inode changed")
        finally:
            os.close(lock_fd)
    finally:
        os.close(fd)
    print("ADMISSION_LOCK_PROVISION=PASS")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.parse_args(argv)
    provision()


if __name__ == "__main__":
    main()
