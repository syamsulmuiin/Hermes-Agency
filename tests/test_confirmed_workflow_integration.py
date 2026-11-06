"""Full trusted workflow acknowledgement integration on a local Unix socket.

Uses the real SQLite store, credential verifier, workflow coordinator and
bounded listener. Cross-UID isolation requires separate host acceptance.
"""
import os
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
from agency.trusted_client import send_stage_confirmed


class ConfirmedWorkflowIntegrationTests(unittest.TestCase):
    def test_real_credentials_ack_and_persisted_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            store = SecureAgencyStore(directory + "/workflow.db")
            try:
                runtime = PortableAgentRuntime(WorkflowCoordinator(store))
                service = TrustedApprovalService(
                    store, b"test-only-credential-secret-long-enough"
                )
                boundary = TrustedAgentExecution(runtime, service)
                task = runtime.start("Acknowledged integrated workflow")
                wrong = service.issue_credential("pm", "worker")
                correct = service.issue_credential("ceo", "worker")
                result = {"completed": [], "output": [], "notes": [], "blockers": []}
                path = directory + "/trusted.sock"
                outcomes = []
                errors = []

                def client():
                    try:
                        for _ in range(200):
                            if os.path.exists(path):
                                break
                            time.sleep(0.01)
                        try:
                            send_stage_confirmed(path, task, "ceo", result, wrong)
                        except PermissionError:
                            outcomes.append("denied")
                        else:
                            outcomes.append("unexpected acceptance")
                        outcomes.append(send_stage_confirmed(
                            path, task, "ceo", result, correct
                        ))
                    except Exception as exc:
                        errors.append(exc)

                thread = threading.Thread(target=client)
                thread.start()
                try:
                    counts = serve_bounded(
                        path, boundary, frozenset({os.getuid()}),
                        max_connections=2, acknowledged=True
                    )
                finally:
                    thread.join(timeout=6)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(outcomes, ["denied", True])
                self.assertEqual(counts, {"accepted": 1, "denied": 1})
                self.assertEqual(runtime.snapshot(task)["owner"], "pm")
                self.assertFalse(os.path.lexists(path))
            finally:
                store.close()
