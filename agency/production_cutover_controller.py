"""Transactional fenced broker cutover controller.

No live systemd adapter is exposed until production attestation is complete.
The deterministic state machine can be acceptance-tested with an isolated
adapter; failure triggers rollback while the admission drain remains held.
"""
from dataclasses import dataclass


class CutoverError(RuntimeError):
    pass


@dataclass(frozen=True)
class CutoverResult:
    status: str
    steps: tuple


def cutover(adapter):
    """Run one authorized cutover with a validated adapter.

    Required operations:
      admission_drain() -> context manager holding exclusive lock
      attest() -> None, fails closed on stale code or nonexclusive state
      freeze() -> None, rejects new jobs before stopping old sidecar
      quiesce() -> None, waits for active jobs to finish
      stop_old() -> None, stop and verify legacy broker
      bootstrap() -> None, durable journal bootstrap/recovery
      start_new() -> None, start and verify fenced broker
      route_new() -> None, change sidecar broker socket and verify
      replay_probe() -> None, prove consumed grant cannot execute twice
      health() -> None, prove new path healthy
      rollback() -> None, restore old route/service WITHOUT restoring ledger
      unfreeze() -> None, reopen admission after successful health/rollback
    """
    steps = []
    with adapter.admission_drain():
        try:
            adapter.attest()
            steps.append("attested")
            adapter.freeze()
            steps.append("frozen")
            adapter.quiesce()
            steps.append("quiesced")
            adapter.stop_old()
            steps.append("old_stopped")
            adapter.bootstrap()
            steps.append("journal_ready")
            adapter.start_new()
            steps.append("new_started")
            adapter.route_new()
            steps.append("new_routed")
            adapter.replay_probe()
            steps.append("replay_denied")
            adapter.health()
            steps.append("healthy")
        except Exception as primary:
            try:
                # Even a partially completed step may have side effects.
                adapter.rollback()
                steps.append("rolled_back")
                adapter.health()
                steps.append("rollback_healthy")
                adapter.unfreeze()
            except Exception as rollback_error:
                # A durable independent freeze gate is mandatory for any
                # real adapter: releasing a process lock alone is not safe.
                adapter.quarantine()
                raise CutoverError("Cutover failed; rollback unverified; durable quarantine required") from rollback_error
            raise CutoverError("Cutover failed; verified rollback restored legacy route") from primary
        try:
            adapter.unfreeze()
        except Exception as unfreeze_error:
            # A failed release after a successful handover is not success.
            # Never return PASS or assume admission has safely reopened.
            adapter.quarantine()
            raise CutoverError(
                "Cutover handover completed but admission unfreeze failed; "
                "durable quarantine required") from unfreeze_error
        steps.append("unfrozen")
    return CutoverResult("PASS", tuple(steps))


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Cutover simulation only")
    parser.add_argument("--simulate", action="store_true", required=True)
    parser.parse_args(argv)
    from .production_cutover_simulation import SimulatedAdapter
    result = cutover(SimulatedAdapter())
    print("CUTOVER_SIMULATION=" + result.status)
    print("CUTOVER_STEPS=" + ",".join(result.steps))


if __name__ == "__main__":
    main()
