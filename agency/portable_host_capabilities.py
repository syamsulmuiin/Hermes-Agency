"""Read-only Linux VPS capability inventory; never selects an unsafe fallback."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


def _probe_command(argv, runner):
    try:
        result = runner(argv, capture_output=True, text=True, timeout=5,
                        check=False)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def inventory(which=shutil.which, runner=subprocess.run,
              exists=lambda p: Path(p).exists()):
    systemd = which("systemctl")
    systemd_live = bool(systemd and exists("/run/systemd/system")
                        and _probe_command([systemd, "show", "--property=Version"],
                                           runner))
    bwrap = which("bwrap")
    return {
        "schema": "hermes-host-capabilities-v1",
        "os": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "systemd": {"binary_found": bool(systemd), "manager_reachable": systemd_live},
        "sandbox": {
            "bubblewrap_binary_found": bool(bwrap),
            "bubblewrap_isolation_validated": False,
            "independent_backend_validated": False,
        },
        "host_paths": {
            "proc_available": exists("/proc/self/status"),
            "run_available": exists("/run"),
            "cgroup_v2_available": exists("/sys/fs/cgroup/cgroup.controllers"),
        },
        "security": {
            "host_compatible": (platform.system() == "Linux" and systemd_live
                                and exists("/proc/self/status")
                                and exists("/run")),
            "sandbox_execution_authorized": False,
            "production_cutover_authorized": False,
        },
        "note": "Presence is not security validation. No sandbox backend is enabled by this report.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    report = inventory()
    print(json.dumps(report, indent=2, sort_keys=True))
    print("PORTABLE_HOST_AUDIT=COMPATIBLE_BASELINE" if
          report["security"]["host_compatible"] else
          "PORTABLE_HOST_AUDIT=UNSUPPORTED_BASELINE")
    print("PRODUCTION_CUTOVER_GO=NO")
    return 0 if report["security"]["host_compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
