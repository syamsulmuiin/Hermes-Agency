# Hermes Agency — Project State

## Mission
Develop a secure, persistent, testable multi-agent runtime while preserving the six original agent prompt templates.

## Repositories
- Upstream (read-only): https://github.com/malvinjauhari/Hermes-Agency
- Fork: https://github.com/syamsulmuiin/Hermes-Agency
- Development branch: development/foundation
- Default branch main remains unchanged by this phase.

## Standing constraints
- Do not change features or behavior outside approved scope.
- Privileged, destructive, credential-related, and deployment actions require explicit authorization.
- Validate changes with tests; maintain rollback paths.
- Do not claim unexecuted actions or tests.
- Technical documentation in English; conversation in Indonesian.
- Preserve upstream attribution and license.

## Phase 1 status
- Fork verified with push permissions.
- Foundation prototype integrated into a separate development branch.
- SQLite tasks, handoffs, audit events; owner validation; deny-by-default example.
- Four local unit tests in tests/test_core.py.
- Original six agents and prompt files remain unchanged.
- Not merged into main or deployed.

## Known limitations
- No real LLM provider, tool execution, sandbox, durable scheduler, user approval flow, or self-improvement.
- set_status currently accepts any enumerated state transition; transitions and authorization need hardening.
- No handoff idempotency, payload size bounds, or audit integrity guarantees.
- Local tests are not a production security assessment.

## Next milestones
1. Add transition graph and owner-aware authorization.
2. Add idempotency keys and transactional task claiming.
3. Add strict schema, size limits, and adversarial tests.
4. Implement actual policy enforcement and approval persistence before tools.
5. Introduce isolated execution, rollback, and recovery.
6. Add agent adapters and measurable learning only after safety gates.

## Continuation prompt
Read PROJECT_STATE.md, inspect the current branch and commits, run tests, preserve upstream templates and scope constraints, then continue the next unfinished milestone. Report evidence, limitations, and blockers.
