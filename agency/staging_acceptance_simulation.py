"""Fail-closed acceptance phase ledger for an isolated staging runner.

This is an offline dependency-injected state-machine test harness, NOT a
host installer. Real PID1 execution is deliberately not implemented.
"""

PHASES = ("snapshot", "isolation", "install", "startup_gate",
          "broker_crash", "pid1_recovery", "replay", "rollback")


def simulate(checks):
    """Require all phases in order; failure must not authorize execute."""
    results = []
    for phase in PHASES:
        try:
            callback = checks[phase]
            ok = callback()
        except Exception as exc:
            results.append({"phase": phase, "result": "DENIED",
                            "reason": type(exc).__name__})
            break
        if ok is not True:
            results.append({"phase": phase, "result": "DENIED",
                            "reason": "NOT_ATTESTED"})
            break
        results.append({"phase": phase, "result": "SIMULATED_PASS"})
    return {"schema": "hermes-staging-acceptance-simulation-v1",
            "phases": results,
            "simulation_complete": len(results) == len(PHASES) and
                                   all(x["result"] == "SIMULATED_PASS" for x in results),
            "real_pid1_tested": False,
            "real_recovery_tested": False,
            "execute_authorized": False,
            "production_mutated": False}
