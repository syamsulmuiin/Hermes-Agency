# Single-VPS trusted service deployment (draft; not yet production-accepted)

This is a **single-host** architecture. The trusted service and agent workers
use different local Linux UIDs, not different VPS instances. Never run the
trusted service as root, expose its socket over TCP, or grant workers access
to the trusted state directory.

## Supervisor

The runner supports `python3 -m agency.single_vps_service --forever`.
A supervisor such as systemd should launch it under a dedicated non-root
service account, with an explicit `User=`, `Group=`, `WorkingDirectory=`,
`ExecStart=`, `Restart=on-failure`, and `NoNewPrivileges=yes`.
The command requires `--socket`, `--state-dir`, `--database`,
`--key-dir`, `--client-gid`, `--allow-uid`, and `--secret-file`.
Do not copy placeholder UID/GID or paths into production.

The trusted state and key directories must be owned by the service UID and
mode 0700; SQLite database and the raw 64-byte signing secret must be 0600.
The separate socket directory must be service-owned, dedicated-client-group
owned, mode 0710; the socket is created 0660. Keep the trusted state outside
the socket directory. Do not grant workers access to secret material.

Use `python3 -m agency.deployment_preflight` as a read-only permissions
check **under the intended service account** before startup.

## Acceptance gate

1. CI unit tests pass, including lifecycle and protected startup tests.
2. A separate, unprivileged client UID can connect using a valid
   worker credential and receives an explicit acknowledgement.
3. Wrong UID and wrong worker credential are rejected, without a workflow
   transition; the client cannot read trusted SQLite or signing secrets.
4. The supervisor survives idle periods, restarts on unexpected failure,
   and preserves SQLite workflow state across restart.
5. No shell, filesystem mutation, network tool, or independent sandbox is
   enabled until the independent sandbox has its own isolation proof.

This document is **not** evidence that the above host-level tests passed.
The trusted service currently processes authenticated, caller-supplied
structured stage results; it does not autonomously generate six-agent work.
