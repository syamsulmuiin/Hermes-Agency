# Foundation prototype

This additive module preserves all upstream prompt templates. It implements local SQLite task persistence, handoff validation, owner checks, an audit log, and a deliberately fail-closed example authorization function.

Run: `python -m unittest discover -s tests -v`

This is not a production policy engine or autonomous runtime. No LLM calls, command execution, scheduling, real approvals, sandbox, or rollback are implemented.
