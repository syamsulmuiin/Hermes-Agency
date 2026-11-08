# Isolated admission behavioral acceptance

This executable acceptance uses the existing `IsolatedHostBackend` and real
Linux processes to test flock contention, exclusive drain, and inode
replacement. It creates only temporary files and does not access the
production admission lock, production journal, route or systemd services.

```bash
cd /root/Hermes-Agency
git pull --ff-only origin development/foundation
python3 -m unittest tests.test_isolated_admission_behavioral_acceptance -v
python3 -B -m agency.isolated_admission_behavioral_acceptance --isolated
```

A passing isolated test is not evidence that the running sidecar participates
in the same lock protocol. The six-blocker production report remains NO_GO.
The next behavioral probes must independently attest live sidecar participation
without changing the production freeze, then test disposable PID1 recovery and
empty-/run provisioning before any maintenance authorization.
