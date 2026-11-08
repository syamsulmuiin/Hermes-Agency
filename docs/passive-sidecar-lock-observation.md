# Passive live lock observation and staging behavioral acceptance

The passive probe samples Linux `/proc/locks` for a bounded interval and
matches FLOCK records to the verified sidecar PID and admission-lock
device/inode. It never sends requests or acquires locks. No observation is
not a failure: short-lived locks may be missed. A positive observation
is evidence of a held lock, not proof of the complete admission protocol.

Run regression and existing isolated real-process behavioral acceptance:

```bash
python3 -m unittest tests.test_passive_sidecar_lock_observation tests.test_isolated_admission_behavioral_acceptance -v
python3 -B -m agency.isolated_admission_behavioral_acceptance --isolated
```

Run the passive live observation without changing production:

```bash
python3 -B -m agency.passive_sidecar_lock_observation --passive --seconds 3
```

The passive probe exits 2 by design. Existing staging admission behavior
must be separately validated on its isolated socket and lock; the
real-process lock fixture is not a complete staging-sidecar test. Production
remains NO_GO. Do not remove freeze, provision the production journal, or
change services or routes.
