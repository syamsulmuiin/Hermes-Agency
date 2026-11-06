"""Single integration test for Phase 5 trusted workflow.

The test exercises the complete local request path. It does not claim
cross-UID isolation, daemon supervision, or tool execution.
"""
import json
import os
import socket
import tempfile
import threading
import time
import unittest

from agency.orchestrator import WorkflowCoordinator
from agency.portable_runtime import PortableAgentRuntime
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.trusted_execution import TrustedAgentExecution
from agency.trusted_service import serve_bounded


class PhaseFiveIntegrationTests(unittest.TestCase):
    def test_local_authenticated_stage_and_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            store = SecureAgencyStore(directory + "/workflow.db")
            runtime = PortableAgentRuntime(WorkflowCoordinator(store))
            service = TrustedApprovalService(store, b"phase-five-test-only-secret-32bytes")
            boundary = TrustedAgentExecution(runtime, service)
            task_id = runtime.start("Phase five integrated workflow")
            result = {"completed": [], "output": [], "notes": [], "blockers": []}
            good = service.issue_credential("ceo", "worker")
            wrong = service.issue_credential("pm", "worker")
            path = directory + "/trusted.sock"
            client_errors = []
            def send_requests():
                try:
                    for _ in range(200):
                        if os.path.exists(path):
                            break
                        time.sleep(0.01)
                    if not os.path.exists(path):
                        raise AssertionError("Socket was not created")
                    for credential in (wrong, good):
                        payload = json.dumps({
                            "task_id": task_id, "agent": "ceo",
                            "result": result, "worker_credential": credential,
                        }).encode()
                        with socket.socket(socket.AF_UNIX) as client:
                            client.connect(path)
                            client.sendall(payload)
                            client.shutdown(socket.SHUT_WR)
                except Exception as exc:
                    client_errors.append(exc)

            # Keep the SQLite-owning thread as the trusted server thread.
            thread = threading.Thread(target=send_requests)
            thread.start()
            try:
                outcome = serve_bounded(path, boundary, frozenset({os.getuid()}), 2)
            finally:
                thread.join(timeout=6)
            self.assertFalse(thread.is_alive())
            self.assertFalse(client_errors, client_errors)
            self.assertEqual(outcome, {"accepted": 1, "denied": 1})
            self.assertEqual(runtime.snapshot(task_id)["owner"], "pm")
            self.assertFalse(os.path.lexists(path))
            store.close()
