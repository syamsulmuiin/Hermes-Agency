# Production readiness evidence synthesis

Run `python3 -B -m agency.production_readiness_synthesis --read-only`.

This command performs only existing read-only sidecar runtime identity and
installed PID1 recovery wiring checks. It does not connect to the operator
socket, acquire admission locks, execute staging, provision journals, change
routes, restart services, or remove freeze.

The report distinguishes fresh host observations from previously reported
staging acceptance. Historical PASS values are not revalidated by this command.
Passive kernel observation remains inconclusive; a non-observed short-lived
shared lock cannot be treated as a failure or success.

All six existing production acceptance blockers remain NOT_ATTESTED. This
report cannot authorize maintenance or cutover; the decision is always NO_GO
and exit status 2 is intentional. Existing
`agency.production_six_blocker_acceptance` remains the authoritative
non-authorizing six-blocker collector.
