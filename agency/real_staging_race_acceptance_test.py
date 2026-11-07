"""Opt-in real multiprocess staging journal launch/recovery race acceptance."""
import argparse
import multiprocessing as mp
import os
import secrets
import sqlite3
import tempfile
import time

from .fenced_staging_serialization import staging_launch, staging_recover
from .fenced_unit_journal import _connect
from .fenced_startup_gate import require_recovered


def child_launch(journal, unit, entered, release, result):
    try:
        def launch():
            entered.set()
            if not release.wait(10):
                raise TimeoutError("Launch hold timed out")
        staging_launch(journal, unit, launch)
        result.put(("launch", "ok"))
    except BaseException as exc:
        result.put(("launch", repr(exc)))


def child_recover(journal, stopped, result):
    try:
        def stop(unit):
            stopped.put(unit)
            return True
        units = staging_recover(journal, stop_unit=stop)
        result.put(("recover", units))
    except BaseException as exc:
        result.put(("recover", repr(exc)))


def child_competing_launch(journal, unit, result):
    try:
        staging_launch(journal, unit, lambda: None)
        result.put(("competing", "unexpectedly admitted"))
    except PermissionError:
        result.put(("competing", "denied"))
    except BaseException as exc:
        result.put(("competing", repr(exc)))


def exercise():
    if os.geteuid() != 0:
        raise PermissionError("Root staging test required")
    ctx = mp.get_context("fork")
    with tempfile.TemporaryDirectory(prefix="hermes-race-", dir="/run") as folder:
        journal = folder + "/owned.sqlite"
        with _connect(journal):
            pass
        unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
        other = "hermes-fenced-" + secrets.token_hex(16) + ".service"
        entered, release = ctx.Event(), ctx.Event()
        results, stopped = ctx.Queue(), ctx.Queue()
        launch = ctx.Process(target=child_launch, args=(journal, unit, entered, release, results))
        recover = ctx.Process(target=child_recover, args=(journal, stopped, results))
        competing = ctx.Process(target=child_competing_launch, args=(journal, other, results))
        processes = (launch, recover, competing)
        try:
            launch.start()
            if not entered.wait(5):
                raise AssertionError("Launch never acquired lock")
            recover.start()
            time.sleep(.2)
            if not stopped.empty() or not results.empty():
                raise AssertionError("Recovery bypassed live launch lock")
            print("RACE_RECOVERY_BLOCKED_DURING_LAUNCH=PASS", flush=True)
            release.set()
            launch.join(8)
            recover.join(8)
            if launch.exitcode != 0 or recover.exitcode != 0:
                raise AssertionError("Launch/recovery process failed")
            seen = [results.get(timeout=2) for _ in range(2)]
            if ("launch", "ok") not in seen or ("recover", (unit,)) not in seen:
                raise AssertionError("Recovery failed to serialize after launch: " + repr(seen))
            if stopped.get(timeout=2) != unit:
                raise AssertionError("Recovery did not stop exact registered unit")
            require_recovered(journal)
            print("RACE_RECOVERY_AFTER_LAUNCH=PASS", flush=True)
            # A second pending launch must block all new launch admission.
            staging_launch(journal, unit_for_second := other, lambda: None)
            competing_unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
            competing = ctx.Process(target=child_competing_launch, args=(journal, competing_unit, results))
            competing.start()
            competing.join(8)
            if competing.exitcode != 0 or results.get(timeout=2) != ("competing", "denied"):
                raise AssertionError("Pending gate admitted competing launch")
            print("RACE_PENDING_GATE_DENIES_NEW_LAUNCH=PASS", flush=True)
            staging_recover(journal, stop_unit=lambda _: True)
            require_recovered(journal)
            print("RACE_POST_RECOVERY_GATE=PASS", flush=True)
        finally:
            release.set()
            for proc in processes:
                if proc.pid is not None:
                    if proc.is_alive():
                        proc.kill()
                    proc.join(3)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    exercise()


if __name__ == "__main__":
    main()
