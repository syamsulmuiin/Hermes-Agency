"""Offline trusted-UID operator verifier provisioning; no plaintext storage."""
import argparse
import getpass
import json
import os
import stat

from .operator_auth import LocalOperatorGate


def provision_operator_verifier(path, identity, secret_hex):
    if (os.geteuid() == 0 or not os.path.isabs(path)
            or not isinstance(identity, str) or not identity
            or len(identity) > 128):
        raise PermissionError("Trusted non-root operator verifier provisioning only")
    parent = os.lstat(os.path.dirname(path))
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700):
        raise PermissionError("Verifier directory must be trusted-owner-only")
    if (type(secret_hex) is not str or len(secret_hex) != 64
            or any(c not in "0123456789abcdef" for c in secret_hex)):
        raise PermissionError("Operator secret must be 32 random bytes as lowercase hex")
    salt, verifier = LocalOperatorGate.provision(bytes.fromhex(secret_hex))
    record = {"identity": identity, "salt_hex": salt.hex(),
              "verifier_hex": verifier.hex()}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            json.dump(record, stream, separators=(",", ":"))
    finally:
        if fd >= 0:
            os.close(fd)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline trusted operator verifier provisioning")
    parser.add_argument("--path", required=True)
    parser.add_argument("--identity", required=True)
    args = parser.parse_args(argv)
    secret = getpass.getpass("Enter operator secret (64 lowercase hex): ").strip()
    second = getpass.getpass("Repeat operator secret: ").strip()
    if secret != second:
        parser.error("Operator secret confirmation mismatch")
    try:
        provision_operator_verifier(args.path, args.identity, secret)
    except (OSError, PermissionError, ValueError):
        parser.error("Operator verifier provisioning denied")
    print("operator_verifier_provisioned=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
