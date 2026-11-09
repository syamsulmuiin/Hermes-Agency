"""Read-only handoff contract for the six private Hermes ChatGPT agent plugins.

This module is not an authentication mechanism, plugin connector, tool executor,
or replacement for the trusted broker. No database writes or external calls.
"""
import hashlib
import json
from .orchestrator import DEFAULT_ROUTE, FIELDS

# These are private ChatGPT plugin package identifiers, NOT credentials or
# authenticated principals. Operator-controlled bindings only.
PLUGIN_IDS = {
    "ceo": "plugins_6af247ef0a94819181a489ed8ee0a295",
    "pm": "plugins_6af248a922ec81918d1e4a759bd3da31",
    "researcher": "plugins_6af2493cc73c81919c521f2801e7a9dd",
    "developer": "plugins_6af24949d2f48191b2163a738c3b8a39",
    "designer": "plugins_6af249571e348191ae268a11c575ff04",
    "qa": "plugins_6af249640a4c8191b3b392f0af45b590",
}

THREAD_IDS = {"ceo": 1, "pm": 3, "researcher": 7,
              "developer": 6, "designer": 4, "qa": 8}


def validate_result(result):
    """Validate an untrusted plugin response using the existing stage schema."""
    if not isinstance(result, dict) or set(result) != FIELDS:
        raise ValueError("Invalid stage result")
    if not all(
        isinstance(items, list) and len(items) <= 100
        and all(isinstance(item, str) and len(item) <= 4096 for item in items)
        for items in result.values()
    ):
        raise ValueError("Invalid stage result content")
    encoded = json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > 65536:
        raise ValueError("Oversized stage result")
    return encoded


def prepare_handoff(workflow, task_id, agent, plugin_id, result):
    """Build a non-executing, validated handoff preview from persisted state.

    The plugin ID is informational, not proof of caller identity. The result
    MUST NOT be sent to WorkflowCoordinator.advance without separately verified
    server-side authorization and the existing fencing/lease controls.
    """
    if not isinstance(task_id, str) or not task_id or len(task_id) > 256:
        raise ValueError("Invalid task ID")
    if not isinstance(agent, str) or agent not in DEFAULT_ROUTE:
        raise ValueError("Unknown agent")
    if not isinstance(plugin_id, str) or plugin_id != PLUGIN_IDS[agent]:
        raise PermissionError("Plugin role binding mismatch")
    encoded = validate_result(result)
    state = workflow.snapshot(task_id)
    route = state["route"]
    index = state["stage"]
    if (state["finished"] or state["status"] != "pending"
            or state["owner"] != agent or not isinstance(route, list)
            or index < 0 or index >= len(route) or route[index] != agent):
        raise PermissionError("No pending stage owned by agent")
    recipient = route[index + 1] if index + 1 < len(route) else None
    return {
        "schema_version": 1,
        "task_id": task_id,
        "stage": index,
        "from_agent": agent,
        "from_thread_id": THREAD_IDS[agent],
        "source_plugin_id": plugin_id,
        "to_agent": recipient,
        "to_thread_id": THREAD_IDS[recipient] if recipient else None,
        "result": json.loads(encoded),
        "result_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "mode": "preview_only",
    }
