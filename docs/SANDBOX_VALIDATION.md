# Phase 5G — Linux sandbox probe (VPS)

This is a **non-destructive capability test**, not an agent executor. It runs
only a fixed `/bin/true` command inside Bubblewrap, with network namespace
isolation, read-only system bind mounts, a private temporary directory,
an empty environment, a timeout, and conservative process rlimits.

## Run on the intended Linux VPS

Run as an **unprivileged account**; do not run as root. Do not disable kernel
protections or change user-namespace sysctls just to make the test pass.

```bash
git clone --branch development/foundation https://github.com/syamsulmuiin/Hermes-Agency.git
cd Hermes-Agency
python3 -m unittest discover -s tests -v
command -v bwrap || echo "Bubblewrap missing"
python3 -c 'from agency.sandbox import sandbox_probe; print(sandbox_probe())'
```

If Bubblewrap is missing, report that fact before installing anything. On
Debian/Ubuntu, an administrator may install it after reviewing host policy:
`sudo apt-get install bubblewrap`. Re-run the probe as the unprivileged user.

Expected success: `{'isolated_probe': True, 'agent_tools_enabled': False,
'resource_limits': 'rlimit-probe-only'}`. If it fails, collect only:
`uname -a`, `bwrap --version`, `id`, and the Python exception output.
Do not share secrets or private key files.

## Security limitations

- Unit tests mock Bubblewrap; they cannot prove host isolation.
- RLIMIT_AS, CPU, file size and file descriptors are process limits, **not**
  a cgroup memory/CPU quota, seccomp policy, or comprehensive sandbox.
- No real agent commands, arbitrary tools, host writes, deployment, or network
  access are permitted by this probe.
- Host-specific namespace policy, kernel capabilities and container nesting
  must be verified before any executor is designed.
- A trusted separate-process service, tool-side fencing, durable idempotency,
  cgroup limits and a disposable writable workspace are still required.
