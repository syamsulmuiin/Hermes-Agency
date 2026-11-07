"""Continuous, fail-closed single-VPS trusted service lifecycle.

The existing worker-stage listener remains unchanged. The operator endpoint
is opt-in, strictly separate from worker transport, and starts only after
explicit root-operator configuration and protected verifier validation.
"""
import os
import socket
import threading

from .single_vps_service import run_service


def _operator_boundary_factory(database, secret):
    from .security import SecureAgencyStore
    from .orchestrator import WorkflowCoordinator
    from .portable_runtime import PortableAgentRuntime
    from .trusted import TrustedApprovalService
    from .trusted_execution import TrustedAgentExecution

    store = SecureAgencyStore(database)
    try:
        runtime = PortableAgentRuntime(WorkflowCoordinator(store))
        service = TrustedApprovalService(store, secret)
        return TrustedAgentExecution(runtime, service), store.close
    except BaseException:
        store.close()
        raise


def serve_forever(socket_path, state_dir, database, key_dir, client_gid,
                  allowed_uids, secret, should_stop=None, operator_config=None):
    """Serve worker requests, optionally alongside owner-only operator IPC.

    The optional operator channel uses separate SQLite connections and denies
    any UID except the explicitly configured root local operator.
    """
    if should_stop is None:
        should_stop = lambda: False
    if not callable(should_stop):
        raise TypeError("Stop predicate required")
    errors = []
    stop_event = threading.Event()
    operator_thread = None
    if operator_config is not None:
        from .operator_control import load_operator_verifier, serve_operator_forever
        from .trusted_broker_adapter import _trusted_key

        if (not isinstance(operator_config, dict)
                or set(operator_config) != {
                    "socket_path", "verifier_path", "broker_key_path", "broker_socket_path"
                }):
            raise ValueError("Invalid operator configuration")
        op_socket = operator_config["socket_path"]
        if (not isinstance(op_socket, str) or not os.path.isabs(op_socket)
                or os.path.abspath(op_socket) == os.path.abspath(socket_path)
                or os.path.dirname(os.path.abspath(op_socket)) ==
                    os.path.dirname(os.path.abspath(socket_path))):
            raise PermissionError("Operator and worker transports must be separate")
        if not all(isinstance(operator_config[k], str)
                   and os.path.isabs(operator_config[k])
                   for k in ("verifier_path", "broker_key_path", "broker_socket_path")):
            raise PermissionError("Operator paths must be absolute")

        verifier = load_operator_verifier(operator_config["verifier_path"])
        _trusted_key(operator_config["broker_key_path"])

        def operator_worker():
            try:
                serve_operator_forever(
                    op_socket,
                    lambda: _operator_boundary_factory(database, secret),
                    verifier, operator_config["broker_key_path"],
                    operator_config["broker_socket_path"], stop_event.is_set,
                )
            except BaseException as exc:
                errors.append(exc)
                stop_event.set()

        operator_thread = threading.Thread(
            target=operator_worker, name="hermes-local-operator", daemon=True
        )
        operator_thread.start()
    handled = 0
    try:
        while not should_stop():
            if errors:
                raise RuntimeError("Authenticated operator listener failed") from errors[0]
            try:
                run_service(socket_path, state_dir, database, key_dir,
                            client_gid, allowed_uids, secret)
            except socket.timeout:
                continue
            handled += 1
        if errors:
            raise RuntimeError("Authenticated operator listener failed") from errors[0]
        return handled
    finally:
        stop_event.set()
        if operator_thread is not None:
            operator_thread.join(timeout=3)
