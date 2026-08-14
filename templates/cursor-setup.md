# Cursor Setup Guide

## How to Implement Hermes Agency in Cursor IDE

### Step 1: Create Agent Profiles

In Cursor, use **Custom Instructions** for each agent:

1. Open Cursor Settings
2. Go to **Features** → **Custom Instructions**
3. Create a new instruction profile for each agent
4. Paste the system prompt content

### Step 2: Agent Setup

| Agent | Profile Name | System Prompt File |
|-------|-------------|-------------------|
| CEO | hermes-ceo | `prompts/01-ceo-agent.md` |
| Project Manager | hermes-pm | `prompts/02-project-manager-agent.md` |
| Researcher | hermes-researcher | `prompts/03-researcher-agent.md` |
| Developer | hermes-developer | `prompts/04-developer-agent.md` |
| Designer | hermes-designer | `prompts/05-designer-agent.md` |
| QA | hermes-qa | `prompts/06-qa-agent.md` |

### Step 3: Project Structure

Create this structure in your workspace:

```
your-project/
├── .cursor/
│   └── rules/
│       ├── ceo-agent.md          # CEO instructions
│       ├── pm-agent.md           # PM instructions
│       ├── researcher-agent.md   # Researcher instructions
│       ├── developer-agent.md    # Developer instructions
│       ├── designer-agent.md     # Designer instructions
│       ├── qa-agent.md           # QA instructions
│       └── shared-rules.md       # Rules for all agents
├── docs/
│   ├── brief.md                  # CEO output
│   ├── research.md               # Researcher output
│   ├── tdd.md                    # PM output
│   └── designs/                  # Designer output
└── src/                          # Developer output
```

### Step 4: Using .cursorrules

Add a `.cursorrules` file at your project root:

```markdown
# Hermes Agency Rules

## Agent Context
This project uses a multi-agent workflow.
Read the shared rules at .cursor/rules/shared-rules.md

## Current Agent
Switch between agent profiles using Cursor's instruction selector.

## File Organization
- docs/brief.md - Project requirements (CEO)
- docs/research.md - Tech recommendations (Researcher)
- docs/tdd.md - Technical design (PM)
- docs/designs/ - UI/UX assets (Designer)
- src/ - Source code (Developer)
```

### Step 5: Workflow

1. Open Cursor and select **hermes-ceo** profile
2. Share client requirements in chat
3. Save CEO output to `docs/brief.md`
4. Switch to **hermes-researcher** profile, read brief
5. Save research to `docs/research.md`
6. Switch to **hermes-pm**, create TDD in `docs/tdd.md`
7. Switch to **hermes-designer**, create mockups in `docs/designs/`
8. Switch to **hermes-developer**, implement in `src/`
9. Switch to **hermes-qa**, test and document in `docs/test-report.md`

### Tips

- Use **Cursor Rules** (`.cursorrules`) for project-wide agent context
- Use **@docs** to reference specific documents in chat
- Use **Composer** for multi-file edits during development
