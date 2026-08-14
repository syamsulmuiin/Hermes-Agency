# Thread Architecture Guide

## Understanding Thread IDs

### What Are Threads?

Threads are isolated conversation contexts for each agent. They allow agents to:

- Maintain their own conversation history
- Reference other agents' work
- Prevent context pollution between roles

### Thread ID Mapping

| Agent | Thread ID | Purpose |
|-------|-----------|---------|
| CEO | 1 | Client conversations, requirements gathering |
| Designer | 4 | Design discussions, mockup reviews |
| Project Manager | 3 | Planning, coordination, status updates |
| Developer | 6 | Implementation, code reviews, bug fixes |
| Researcher | 7 | Technology research, analysis |
| QA | 8 | Testing, bug reports, quality gates |

### How Threads Connect

```
Thread 1 (CEO) ──→ Thread 3 (PM) ──→ Thread 6 (Developer) ──→ Thread 8 (QA)
       │                    │
       └──→ Thread 7 (Researcher)
       │
       └──→ Thread 4 (Designer)
```

### Thread Dependencies

| Agent | Reads From | Writes To |
|-------|-----------|-----------|
| CEO | Client | Thread 1 |
| PM | Thread 1, Thread 7 | Thread 3 |
| Researcher | Thread 1 | Thread 7 |
| Developer | Thread 1, Thread 3, Thread 7 | Thread 6 |
| Designer | Thread 1, Thread 3 | Thread 4 |
| QA | Thread 1, Thread 3, Thread 6 | Thread 8 |

### Implementation by Platform

#### ChatGPT
- Use separate conversations for each thread
- Name conversations: "Hermes CEO", "Hermes PM", etc.
- Copy-paste between conversations for handoffs

#### Claude
- Use Projects for each thread
- Add shared rules to every project's instructions
- Use Project Knowledge for cross-thread documents

#### Custom Implementation
```python
threads = {
    "ceo": [],        # Thread 1
    "pm": [],         # Thread 3
    "developer": [],  # Thread 6
    "designer": [],   # Thread 4
    "researcher": [], # Thread 7
    "qa": [],         # Thread 8
}
```

### Best Practices

1. **Never mix threads** — Keep each agent's context isolated.
2. **Reference, don't copy** — Pass thread IDs, not full histories.
3. **Archive completed threads** — Store finished work for future reference.
4. **Document handoffs** — Always note which thread output came from.
