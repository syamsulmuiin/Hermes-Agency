# Hermes Agency: ChatGPT Agent Plugin Integration (preview-only)

## Status
Six private ChatGPT plugins exist for CEO, Project Manager, Researcher,
Developer, Designer and QA. Their plugin IDs are registered in
`agency/plugin_handoff.py` as **informational bindings only**. This stage
does not connect ChatGPT accounts or authenticate any plugin.

## Current safe contract
`prepare_handoff(workflow, task_id, agent, plugin_id, result)` reads the
persisted workflow snapshot and validates the existing four result fields:
`completed`, `output`, `notes`, `blockers`. It checks the expected
plugin binding and owner/stage, returns a deterministic, hashed,
preview-only handoff envelope, and performs no I/O beyond the snapshot.
It does **not** invoke `advance()`, modify SQLite or call an LLM.

Thread IDs are logical prompt references, not automatically readable
ChatGPT conversations. Handoffs require explicitly supplied and authorized
context; no cross-chat access is assumed.

## Security boundaries
- A plugin ID or thread ID **does not authenticate** a caller.
- Do not treat ChatGPT-generated text or `result_sha256` as an approval,
  identity assertion, signature, or execution capability.
- Never pass the preview to `WorkflowCoordinator.advance()` based only on
  its plugin binding. The existing coordinator accepts an untrusted agent
  label; a separate trusted server-side gate is mandatory.
- Production broker, sandbox, replay ledger, admission freeze and recovery
  protection remain unchanged. No deployment or tool execution is enabled.
- The existing workflow route orders Developer before Designer. The prompt
  dependency map instead places Designer before Developer. This phase
  intentionally does **not** change routing; Project Manager must resolve
  the approved dependency before any real automated flow.

## Next implementation gates
1. Verify approved agent dependency ordering with the CEO/Project Manager.
2. Add trusted caller authentication and role authorization at a separated
   service boundary, not in plugin-provided fields.
3. Bind each write to an authenticated task, stage, fencing token and
   durable replay/idempotency record, without bypassing the fenced broker.
4. Provide an explicit, least-privilege transport for authorized context.
5. Exercise crash/restart, duplicate submissions, missing context, approval,
   denied sandbox, and QA rejection paths in isolated staging.
6. Keep production NO-GO until independent acceptance and explicit approval.

## Verification
`python3 -m unittest tests.test_plugin_handoff -v`
Run the full suite separately. Source code created here has not been
validated against a live ChatGPT plugin session or the production VPS.
