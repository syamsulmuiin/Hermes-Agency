"""Read-only plugin handoff checks; no service or ChatGPT connection required."""
import unittest
from agency.plugin_handoff import PLUGIN_IDS, THREAD_IDS, prepare_handoff, validate_result
from agency.orchestrator import DEFAULT_ROUTE

RESULT = {"completed": ["Reviewed requirements"], "output": ["Project brief"],
          "notes": [], "blockers": []}


class FakeWorkflow:
    def __init__(self, state):
        self.state = state

    def snapshot(self, task_id):
        return dict(self.state)


class PluginHandoffTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(owner="ceo", status="pending",
                          route=list(DEFAULT_ROUTE), stage=0, finished=False)
        self.workflow = FakeWorkflow(self.state)

    def test_all_six_roles_bound(self):
        self.assertEqual(set(PLUGIN_IDS), set(DEFAULT_ROUTE))
        self.assertEqual(set(THREAD_IDS), set(DEFAULT_ROUTE))
        self.assertEqual(len(set(PLUGIN_IDS.values())), 6)

    def test_preview_only_and_stable_digest(self):
        a = prepare_handoff(self.workflow, "task-1", "ceo", PLUGIN_IDS["ceo"], RESULT)
        b = prepare_handoff(self.workflow, "task-1", "ceo", PLUGIN_IDS["ceo"], RESULT)
        self.assertEqual(a, b)
        self.assertEqual(a["mode"], "preview_only")
        self.assertEqual(a["to_agent"], "pm")
        self.assertEqual(a["to_thread_id"], 3)
        self.assertEqual(self.state["stage"], 0)

    def test_wrong_plugin_and_owner_denied(self):
        with self.assertRaises(PermissionError):
            prepare_handoff(self.workflow, "task-1", "ceo", PLUGIN_IDS["qa"], RESULT)
        with self.assertRaises(PermissionError):
            prepare_handoff(self.workflow, "task-1", "qa", PLUGIN_IDS["qa"], RESULT)

    def test_completed_and_unowned_denied(self):
        self.state["finished"] = True
        with self.assertRaises(PermissionError):
            prepare_handoff(self.workflow, "task-1", "ceo", PLUGIN_IDS["ceo"], RESULT)

    def test_last_stage_has_no_recipient(self):
        self.state.update(owner="qa", stage=5)
        a = prepare_handoff(self.workflow, "task-1", "qa", PLUGIN_IDS["qa"], RESULT)
        self.assertIsNone(a["to_agent"])
        self.assertIsNone(a["to_thread_id"])

    def test_invalid_and_oversized_results_denied(self):
        for bad in ({"output": []}, {**RESULT, "output": [7]},
                    {**RESULT, "output": ["X" * 4097]}):
            with self.assertRaises(ValueError):
                validate_result(bad)

    def test_input_object_is_not_modified(self):
        original = {key: list(value) for key, value in RESULT.items()}
        prepare_handoff(self.workflow, "task-1", "ceo", PLUGIN_IDS["ceo"], RESULT)
        self.assertEqual(RESULT, original)


if __name__ == "__main__":
    unittest.main()
