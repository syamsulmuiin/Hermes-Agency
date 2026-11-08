"""Conservative read-only staging isolation observations; never execution authority."""
import os
from pathlib import Path


def inspect(*, readlink=os.readlink, read_text=None):
    """Detect obvious host namespace sharing, not certify a container or VM."""
    if read_text is None:
        read_text = lambda p: Path(p).read_text()
    names = ("pid", "mnt", "net", "ipc", "uts", "user")
    namespaces = {}
    for name in names:
        current = readlink("/proc/self/ns/" + name)
        host_init = readlink("/proc/1/ns/" + name)
        namespaces[name] = {"current": current, "pid1": host_init,
                            "same_as_visible_pid1": current == host_init}
    comm = read_text("/proc/1/comm").strip()
    # A private PID namespace may still share host filesystems and sockets.
    # PID1 being systemd is insufficient evidence of staging isolation.
    return {"schema": "hermes-staging-isolation-observation-v1",
            "visible_pid1": comm, "namespaces": namespaces,
            "filesystem_separation_attested": False,
            "production_socket_separation_attested": False,
            "journal_separation_attested": False,
            "independent_pid1_attested": False,
            "isolation_attested": False,
            "execute_authorized": False,
            "production_mutated": False}
