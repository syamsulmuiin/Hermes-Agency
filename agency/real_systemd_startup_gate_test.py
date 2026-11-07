"""Opt-in real systemd ExecStartPre startup denial test (test-only units).

Creates a uniquely named transient service through systemd-run; its
ExecStartPre runs a test-only gate command, and ExecStart creates a marker.
No production unit files or service overrides are modified.
"""
import argparse
import os
import secrets
import subprocess
import tempfile
import time


def run(*argv):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15, check=False)


def exercise():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Requires isolated root systemd host")
    name = "hermes-gate-test-" + secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix="hermes-gate-", dir="/run") as folder:
        os.chmod(folder, 0o700)
        marker = folder + "/started"
        gate = folder + "/gate"
        with open(gate, "w", encoding="ascii") as file:
            file.write("#!/bin/sh\nexit 1\n")
        os.chmod(gate, 0o700)
        # systemd-run --property=ExecStartPre is not universally supported:
        # install only a uniquely named TEST service under /run/systemd/system.
        path = "/run/systemd/system/" + name + ".service"
        if os.path.lexists(path):
            raise RuntimeError("Test service collision")
        unit = ("[Unit]\nDescription=Hermes isolated startup gate acceptance\n"
                "[Service]\nType=oneshot\n"
                "ExecStartPre=" + gate + "\n"
                "ExecStart=/usr/bin/touch " + marker + "\n")
        try:
            with open(path, "x", encoding="utf-8") as file:
                file.write(unit)
            os.chmod(path, 0o600)
            if run("/usr/bin/systemctl", "daemon-reload").returncode:
                raise RuntimeError("Test daemon reload failed")
            result = run("/usr/bin/systemctl", "start", name + ".service")
            if result.returncode == 0 or os.path.exists(marker):
                raise AssertionError("ExecStart executed despite failing gate")
            print("real_execstartpre_failure_blocks_execstart=PASS", flush=True)
            # Allow gate to succeed, then confirm only test service starts.
            with open(gate, "w", encoding="ascii") as file:
                file.write("#!/bin/sh\nexit 0\n")
            if run("/usr/bin/systemctl", "reset-failed", name + ".service").returncode:
                raise RuntimeError("Could not reset test service")
            if run("/usr/bin/systemctl", "start", name + ".service").returncode:
                raise RuntimeError("Gate success failed to start test service")
            if not os.path.isfile(marker):
                raise AssertionError("ExecStart marker absent after recovery gate passed")
            print("real_execstartpre_success_allows_execstart=PASS", flush=True)
        finally:
            run("/usr/bin/systemctl", "stop", name + ".service")
            if os.path.exists(path):
                os.unlink(path)
            run("/usr/bin/systemctl", "daemon-reload")
            run("/usr/bin/systemctl", "reset-failed", name + ".service")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required for real systemd test")
    exercise()


if __name__ == "__main__":
    main()
