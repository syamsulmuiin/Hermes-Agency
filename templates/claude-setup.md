# Claude Setup Guide

## How to Implement Hermes Agency in Claude

### Step 1: Use Projects

Claude Projects are ideal for multi-agent setups:

1. Go to [claude.ai/projects](https://claude.ai/projects)
2. Create a new Project for each agent
3. Add the system prompt as Project Instructions
4. Upload relevant documents as Project Knowledge

### Step 2: Agent Setup

| Agent | Project Name | System Prompt File |
|-------|-------------|-------------------|
| CEO | Hermes CEO | `prompts/01-ceo-agent.md` |
| Project Manager | Hermes PM | `prompts/02-project-manager-agent.md` |
| Researcher | Hermes Researcher | `prompts/03-researcher-agent.md` |
| Developer | Hermes Developer | `prompts/04-developer-agent.md` |
| Designer | Hermes Designer | `prompts/05-designer-agent.md` |
| QA | Hermes QA | `prompts/06-qa-agent.md` |

### Step 3: Shared Rules Setup

Add `prompts/shared-rules.md` to **every project's instructions** field. This ensures all agents follow the same governance rules.

### Step 4: Workflow

1. Start conversation in **CEO Project**
2. When CEO produces output, copy it to:
   - **Researcher Project** for technology analysis
   - **PM Project** for execution planning
3. Researcher and PM can run in parallel
4. Once PM has TDD, pass to:
   - **Designer Project** for UI/UX
   - **Developer Project** for implementation
5. Developer output goes to **QA Project** for testing

### Step 5: Artifacts

Use Claude's Artifacts feature to:

- Generate structured documents (Project Brief, TDD, Test Report)
- Create diagrams (architecture, user flows)
- Write and test code snippets

### Tips

- Claude's longer context window (200K tokens) handles large project docs well
- Use **Claude Team** for shared projects across your agency
- Export conversations as markdown for documentation
