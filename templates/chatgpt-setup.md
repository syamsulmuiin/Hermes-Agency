# ChatGPT Setup Guide

## How to Implement Hermes Agency in ChatGPT

### Step 1: Create Custom GPTs

For each agent, create a separate Custom GPT:

1. Go to [chat.openai.com/gpts](https://chat.openai.com/gpts)
2. Click **Create a GPT**
3. Name it (e.g., "Hermes CEO Agent")
4. Paste the system prompt from the corresponding `prompts/` file
5. Set instructions to "Always respond in structured format"
6. Save and publish as needed

### Step 2: Agent Setup

| Agent | GPT Name | System Prompt File |
|-------|----------|-------------------|
| CEO | Hermes CEO | `prompts/01-ceo-agent.md` |
| Project Manager | Hermes PM | `prompts/02-project-manager-agent.md` |
| Researcher | Hermes Researcher | `prompts/03-researcher-agent.md` |
| Developer | Hermes Developer | `prompts/04-developer-agent.md` |
| Designer | Hermes Designer | `prompts/05-designer-agent.md` |
| QA | Hermes QA | `prompts/06-qa-agent.md` |

### Step 3: Workflow

1. Start with **CEO GPT** — share client requirements
2. Copy CEO's output to **Researcher GPT** and **PM GPT**
3. PM creates execution plan, Researcher provides tech recommendations
4. Pass plan to **Designer GPT** for mockups
5. Pass designs + plan to **Developer GPT** for implementation
6. Pass code to **QA GPT** for testing

### Step 4: Thread Management

Since ChatGPT doesn't have native thread IDs, use this convention:

- Prefix each conversation with the agent name
- Copy-paste relevant outputs between GPTs
- Keep a shared document (Google Docs, Notion) as your "thread store"

### Tips

- Use **ChatGPT Teams** or **Enterprise** for better conversation management
- Pin important conversations for quick reference
- Use custom instructions to maintain context across sessions
