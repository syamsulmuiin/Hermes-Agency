"""Fail-closed audit of the currently implemented production caller route.

Read-only source inspection; never modifies services, sockets or grants.
"""
import argparse
import inspect

from . import single_vps_service, service_lifecycle, protected_service
from . import trusted_execution, trusted_broker_adapter, cross_uid_listener


def audit():
    assert "serve_forever" in inspect.getsource(single_vps_service.main)
    assert "run_service" in inspect.getsource(service_lifecycle.serve_forever)
    assert "serve_protected_once" in inspect.getsource(single_vps_service.run_service)
    assert "serve_cross_uid_once" in inspect.getsource(protected_service.serve_protected_once)
    assert "execute_operator_approved_job" in inspect.getsource(trusted_execution.TrustedAgentExecution)
    assert "execute_approved_job" in inspect.getsource(trusted_execution.TrustedAgentExecution.execute_operator_approved_job)
    assert "issue_broker_grant" in inspect.getsource(trusted_broker_adapter.execute_approved_job)
    assert "submit_signed_grant" in inspect.getsource(trusted_broker_adapter.execute_approved_job)
    # Current worker listener only delegates to stage-oriented peer/ACK protocol;
    # it does not call the approved-job broker adapter.
    source = inspect.getsource(cross_uid_listener.serve_cross_uid_once)
    if "execute_operator_approved_job" in source or "execute_approved_job" in source:
        raise RuntimeError("Worker-facing broker route needs security review")
    print("TRUSTED_APPROVED_JOB_ADAPTER_PRESENT=PASS")
    print("WORKER_SOCKET_BROKER_ROUTE_EXPOSED=NO")
    print("PRODUCTION_FENCED_CALLER_ROUTE_VERIFIED=NO")
    print("PRODUCTION_CUTOVER_AUTHORIZED=NO")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    audit()


if __name__ == "__main__":
    main()
