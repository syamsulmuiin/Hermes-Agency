# Portable VPS baseline

Run `python3 -B -m agency.portable_host_capabilities --read-only` on each
target host. This inventory does not modify systemd, users, directories,
admission locks, journals, routes, or sandbox policy.

The baseline currently targets Linux hosts with reachable systemd, /proc,
and /run. It reports architecture and available facilities rather than
assuming one VPS's PID, inode, or filesystem layout. A found bubblewrap
binary does not prove namespace isolation: actual sandbox execution remains
disabled until independently validated on that host.

Next phases: introduce validated deployment manifest for service identities
and paths; add installer preflight and disposable-host acceptance; then
replace hardcoded snapshot/unit paths in the existing read-only evidence
collectors without weakening their identity and inode checks. Do not
reinterpret a capability inventory as admission, recovery, or cutover proof.
Production remains NO-GO.
