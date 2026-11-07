"""Isolated exclusive-drain acceptance; never touches production lock or services."""
import argparse
import fcntl
import multiprocessing as mp
import os
from pathlib import Path
import stat
import sys
import tempfile

from .operator_control import operator_admission_lease


def _holder(path, ready, release, results):
    try:
        with operator_admission_lease(path):
            ready.set()
            if not release.wait(10):
                raise TimeoutError("shared holder release timed out")
        results.put("PASS")
    except BaseException as exc:
        ready.set()
        results.put(type(exc).__name__)


def _identity(path):
    info = os.stat(path, follow_symlinks=False)
    if not (stat.S_ISREG(info.st_mode) and info.st_uid == 0
            and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o640):
        raise PermissionError("Unsafe staging lock")
    return (info.st_dev, info.st_ino)


def run():
    if os.geteuid() != 0:
        raise PermissionError("Root required for root-owned staging lock")
    with tempfile.TemporaryDirectory(prefix="hermes-drain-staging-") as directory:
        path = str(Path(directory) / "admission.lock")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o640)
        child = None
        try:
            os.fchmod(fd, 0o640)
            inode = _identity(path)
            ready, release = mp.Event(), mp.Event()
            results = mp.Queue()
            child = mp.Process(target=_holder, args=(path, ready, release, results))
            child.start()
            if not ready.wait(10):
                raise TimeoutError("Shared holder not ready")
            if not child.is_alive():
                raise RuntimeError("Shared holder exited unexpectedly")
            print("DRAIN_SHARED_ADMISSION_ACTIVE=PASS")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("DRAIN_EXCLUSIVE_BLOCKED_BY_SHARED=PASS")
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
                raise AssertionError("Exclusive drain bypassed shared admission")
            release.set()
            child.join(10)
            if child.is_alive() or child.exitcode != 0 or results.get(timeout=2) != "PASS":
                raise RuntimeError("Shared admission failed to finish")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("DRAIN_EXCLUSIVE_AFTER_QUIESCENCE=PASS")
            if _identity(path) != inode or (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != inode:
                raise AssertionError("Lock inode changed")
            print("DRAIN_INODE_STABLE=PASS")
            try:
                with operator_admission_lease(path):
                    raise AssertionError("Admission bypassed exclusive drain")
            except PermissionError:
                print("DRAIN_NEW_ADMISSION_DENIED=PASS")
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
            with operator_admission_lease(path):
                print("DRAIN_ADMISSION_RESUMED=PASS")
            if _identity(path) != inode:
                raise AssertionError("Lock inode changed after drain")
            print("ISOLATED_EXCLUSIVE_DRAIN_E2E=PASS")
            print("PRODUCTION_MUTATED=NO")
            print("PRODUCTION_CUTOVER_GO=NO")
            return 0
        finally:
            if child is not None and child.is_alive():
                release.set()
                child.join(2)
                if child.is_alive():
                    child.terminate()
                    child.join(2)
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolated-test", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        return run()
    except (OSError, ValueError, RuntimeError, TimeoutError, AssertionError) as exc:
        print("ISOLATED_EXCLUSIVE_DRAIN_E2E=NO_GO")
        print("DRAIN_ERROR=" + type(exc).__name__ + ": " + str(exc))
        print("PRODUCTION_CUTOVER_GO=NO")
        return 2


if __name__ == "__main__":
    sys.exit(main())
