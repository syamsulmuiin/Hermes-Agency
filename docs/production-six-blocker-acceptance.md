# Six-blocker production acceptance evidence

The read-only collector `agency.production_six_blocker_acceptance` reuses
`production_readiness_stages --stage1-read-only` and
`fenced_cutover_controller --dry-run`. It does not run the staging E2E,
create a production ownership journal, change routes, stop services, or remove
the admission freeze.

## Run

```bash
cd /root/Hermes-Agency
git pull --ff-only origin development/foundation
python3 -m unittest tests.test_production_six_blocker_acceptance -v
python3 -B -m agency.production_six_blocker_acceptance \
  --output "/tmp/hermes-six-blocker-$(date -u +%Y%m%dT%H%M%SZ).json"
echo "ACCEPTANCE_RC=$?"
```

Exit 2 and `NO_GO` are intentional. The report has six evidence slots:
ownership journal, live sidecar admission, exclusive drain/inode, production
route handover/rollback, independent PID1 recovery, and empty `/run` boot
provisioning. It preserves the raw stage-1 evidence and blockers for review.

An existing staging log may be supplied with `--staging-log /path/to/log`.
Markers are parsed as *untrusted external staging results*, never as
production authorization. The collector does not run or trust any
`--execute` production path.

## Acceptance boundary

A staging journal recovery PASS is reusable engineering evidence but does not
prove a production journal exists. Live sidecar lock participation requires an
independent behavioral test, not just a successful flock. Production route
handover/rollback requires a separately approved maintenance window.
Independent PID1 recovery and boot provisioning need controlled isolation
tests. Never promote missing evidence to PASS or alter
`fenced_cutover_controller.py` to permit execution.

The collector intentionally does not attempt those potentially mutating
acceptance steps. It is an audit artifact and never issues a GO decision.
