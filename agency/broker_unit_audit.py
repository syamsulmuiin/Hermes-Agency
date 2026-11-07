"""Root-only production-unit hardening inspection; no service mutation."""
import argparse
import configparser
import os
import stat


REQUIRED = {
    "Service": {
        "Type": "simple",
        "User": "root",
        "Group": "root",
        "NoNewPrivileges": "yes",
        "PrivateTmp": "yes",
        "ProtectHome": "yes",
        "ProtectSystem": "strict",
        "RestrictAddressFamilies": "AF_UNIX",
        "UMask": "0077",
        "LimitCORE": "0",
        "ProtectKernelTunables": "yes",
        "ProtectKernelModules": "yes",
        "ProtectKernelLogs": "yes",
        "ProtectControlGroups": "yes",
        "ProtectClock": "yes",
        "PrivateDevices": "yes",
        "RestrictSUIDSGID": "yes",
        "LockPersonality": "yes",
        "RestrictRealtime": "yes",
        "SystemCallArchitectures": "native",
    }
}


def check_unit(path):
    if not os.path.isabs(path):
        raise PermissionError("Absolute unit path required")
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    with open(path, encoding="utf-8") as stream:
        parser.read_file(stream)
    for section, expected in REQUIRED.items():
        for field, value in expected.items():
            if parser.get(section, field, fallback=None) != value:
                raise PermissionError("Missing required broker hardening: " + field)
    command = parser.get("Service", "ExecStart", fallback="")
    if ("-m agency.supervised_broker" not in command or
            "--trusted-user hermes-trusted" not in command or
            "--key /etc/hermes-broker/signing.key" not in command):
        raise PermissionError("Wrong signed-only broker entrypoint")
    writable = parser.get("Service", "ReadWritePaths", fallback="").split()
    if set(writable) != {"/run/hermes-broker", "/var/lib/hermes-broker"}:
        raise PermissionError("Broker writable paths not bounded")
    if parser.get("Service", "ExecStartPre", fallback=None) is not None:
        raise PermissionError("Unexpected pre-start command")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("unit")
    args = parser.parse_args()
    check_unit(os.path.abspath(args.unit))
    print("production_unit_static_hardening=PASS")


if __name__ == "__main__":
    main()
