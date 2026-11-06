# Single-VPS trusted service deployment and acceptance

**Status:** Experimental trusted runtime, not production-approved and not autonomous.
One active VPS only. Linux identities separate local processes, not hosts.

## Verified host checkpoint — 2026-11-07

On Ubuntu x86_64, Python 3.12.3, systemd 255, branch
`development/foundation` at commit `6f8c37c`:

- 110/110 Python unit tests passed.
- `hermes-agency.service` was enabled and active under non-root
  `hermes-trusted` (UID 997), with group `hermes-agents` (GID 987).
- `hermes-worker` (UID 995) connected to the Unix socket.
- The worker was denied reading `agency.db` and `signing.key`.
- The socket had owner/group `hermes-trusted:hermes-agents`, mode 0660.

**Not verified on host:** authenticated valid/invalid worker messages,
unauthorized peer UID, persisted workflow across restart, systemd failure
recovery, independent sandbox, model-driven autonomous agent execution.
A bare socket connection is not an authenticated workflow request.

## Installed layout

| Resource | Owner / group | Mode |
|---|---|---|
| `/var/lib/hermes-agency` | trusted / trusted | 0700 |
| `/var/lib/hermes-agency/keys` | trusted / trusted | 0700 |
| `/var/lib/hermes-agency/agency.db` | trusted / trusted | 0600 |
| `/var/lib/hermes-agency/keys/signing.key` | trusted / trusted | 0600 |
| `/run/hermes-agency` | trusted / agents | 0710 |
| `/run/hermes-agency/trusted.sock` | trusted / agents | 0660 |
| `/opt/hermes-agency` | root / root | non-writable by agents |

The signing secret contains 64 **raw** random bytes; never commit, print, or
send it. Do not regenerate it over an existing file: old signed credentials
would become invalid. The original repository remains in
`/root/Hermes-Agency`; the running service uses a separate copy in
`/opt/hermes-agency`. A Git pull alone does **not** deploy new runtime code.

## Service operation

```bash
systemctl status hermes-agency.service --no-pager
journalctl -u hermes-agency.service -n 50 --no-pager
systemctl is-active hermes-agency.service
```

The service runs as `User=hermes-trusted`, `Group=hermes-agents`,
`UMask=0077`, with `ProtectSystem=strict`, `ProtectHome=yes`,
`NoNewPrivileges=yes`, and narrow `ReadWritePaths`. Its entry point is
`python3 -m agency.single_vps_service --forever`, with explicit socket,
state, database, key directory, client GID, allowed UID and secret file.
`Restart=on-failure` is enabled. Runtime code changes require controlled
redeployment and restart; do not change a live installation blindly.

### Preflight

Run the read-only check **as the trusted account**, with real local IDs:

```bash
runuser -u hermes-trusted -- sh -c 'cd /opt/hermes-agency && python3 -m agency.deployment_preflight --transport-dir /run/hermes-agency --state-dir /var/lib/hermes-agency --database /var/lib/hermes-agency/agency.db --key-dir /var/lib/hermes-agency/keys --client-gid 987 --allow-uid 995'
```

These IDs describe the verified host only; do not assume they apply to
another VPS. The `/run` directory was manually created; it may disappear
after reboot. **Persistent boot-time creation of the exact owner/group/mode
is still required** before claiming reliable reboot recovery.

## Outstanding acceptance criteria

1. A real worker UID submits a correctly signed, role-scoped stage request
   and receives an accepted acknowledgement with the expected persisted
   workflow transition.
2. Wrong credential and unauthorized UID fail without changing workflow.
3. Database and signing key remain inaccessible to worker and other users.
4. Restart preserves a nontrivial task state; service restarts on failure;
   boot recreates the socket directory securely.
5. Independent OS-enforced sandbox passes resource, filesystem, process,
   and network isolation tests before any agent-selected tool is enabled.
6. Six model-driven agents perform an authorized end-to-end task with
   approval and QA evidence.

The first four validate the trusted service only. The last two are
**not implemented** and cannot be inferred from unit tests or a running
systemd service. Never bypass these gates by running commands directly on
the host as the agent.
