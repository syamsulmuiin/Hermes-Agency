<p align="center">
  <img src="https://img.shields.io/badge/HERMES-AGENCY-FF6B35?style=for-the-badge&logo=hermes&logoColor=white" alt="Hermes Agency"/>
</p>

<h1 align="center">Hermes Agency</h1>

<p align="center">
  <strong>Multi-Agent AI System Prompt Template</strong><br>
  <em>Build your own AI agency with structured agent roles, shared rules, and proven workflows.</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#agent-roles">Agents</a> •
  <a href="#setup-guides">Setup</a> •
  <a href="README-id.md">Indonesian</a> •
  <a href="#license">License</a>
</p>

---

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"/>
  <img src="https://img.shields.io/badge/Agents-6-blue?style=flat-square" alt="Agents"/>
  <img src="https://img.shields.io/badge/LLM-Any-purple?style=flat-square" alt="LLM"/>
  <img src="https://img.shields.io/badge/Platform-Universal-orange?style=flat-square" alt="Platform"/>
</p>

---

## What is Hermes Agency?

Hermes Agency is a **system prompt template** that transforms any LLM into a structured multi-agent team. It provides pre-built agent roles, governance rules, and workflow patterns for building AI-powered agencies.

**No code required.** Just copy the prompts into your favorite LLM platform.

### Why Use This?

| Problem | Solution |
|---------|----------|
| Single AI lacks specialization | 6 specialized agent roles |
| Agents work in isolation | Shared rules ensure collaboration |
| No clear workflow | Proven handoff patterns included |
| Platform lock-in | Works with any LLM provider |
| Starting from scratch | Production-ready templates |

---

## Features

- **6 Specialized Agents** — CEO, PM, Researcher, Developer, Designer, QA
- **Shared Governance Rules** — Cross-agent coordination and conflict resolution
- **Thread Architecture** — Isolated contexts with structured handoffs
- **Platform Templates** — Setup guides for ChatGPT, Claude, Cursor, and custom APIs
- **Real Examples** — Complete project workflow from client to deployment
- **All LLM Providers** — OpenAI, Anthropic, Google, Mistral, local models

---

## Quick Start

### 1. Clone or Download

```bash
git clone https://github.com/syamsulmuiin/Hermes-Agency.git
cd Hermes-Agency
```

### 2. Choose Your Platform

| Platform | Guide |
|----------|-------|
| ChatGPT | [chatgpt-setup.md](templates/chatgpt-setup.md) |
| Claude | [claude-setup.md](templates/claude-setup.md) |
| Cursor IDE | [cursor-setup.md](templates/cursor-setup.md) |
| Custom LLM API | [custom-llm-setup.md](templates/custom-llm-setup.md) |

### 3. Copy Prompts

Each agent has a system prompt in `prompts/`. Copy the content into your LLM's system instruction field.

### 4. Start Building

1. Begin with **CEO Agent** — share your client's requirements
2. Pass output to **Researcher** and **PM** agents
3. Continue the workflow through **Designer** → **Developer** → **QA**

---

## Agent Roles

| Agent | Thread ID | Responsibility | Output |
|-------|-----------|----------------|--------|
| **CEO** | 1 | Client communication, requirements | Project Brief |
| **Project Manager** | 3 | Execution planning, coordination | Technical Design Document |
| **Designer** | 4 | UI/UX design, mockups | Design System, Wireframes |
| **Developer** | 6 | Code implementation | Source Code, Tests |
| **Researcher** | 7 | Technology research | Research Report, Recommendations |
| **QA** | 8 | Quality assurance | Test Report, Bug Reports |

### Agent Dependency Map

```
Client
   ↓
CEO Agent
   ↓
PM Agent ←→ Researcher Agent
   ↓              ↓
Designer Agent    ↓
   ↓              ↓
Developer Agent ←┘
   ↓
QA Agent
   ↓
Deployment
```

---

## Repository Structure

```
Hermes-Agency/
├── README.md                          # This file (English)
├── README-id.md                       # Indonesian version
├── LICENSE                            # MIT License
│
├── prompts/                           # System prompts for each agent
│   ├── 01-ceo-agent.md
│   ├── 02-project-manager-agent.md
│   ├── 03-researcher-agent.md
│   ├── 04-developer-agent.md
│   ├── 05-designer-agent.md
│   ├── 06-qa-agent.md
│   └── shared-rules.md                # Multi-agent governance rules
│
├── templates/                         # Platform-specific setup guides
│   ├── chatgpt-setup.md
│   ├── claude-setup.md
│   ├── cursor-setup.md
│   ├── custom-llm-setup.md
│   └── thread-architecture.md
│
├── examples/                          # Real-world usage examples
│   ├── client-project-example.md
│   └── agent-handoff-example.md
│
└── assets/                            # Diagrams and references
    └── architecture-diagram.md
```

---

## Setup Guides

### ChatGPT
Create separate Custom GPTs for each agent. Copy system prompts into GPT instructions.

[View ChatGPT Guide →](templates/chatgpt-setup.md)

### Claude
Use Claude Projects for each agent. Add shared rules to every project's instructions.

[View Claude Guide →](templates/claude-setup.md)

### Cursor IDE
Use `.cursor/rules/` directory with agent-specific instruction files.

[View Cursor Guide →](templates/cursor-setup.md)

### Custom LLM API
Python wrapper for any LLM provider (OpenAI, Anthropic, Google, Mistral, local models).

[View Custom Guide →](templates/custom-llm-setup.md)

---

## Thread Architecture

Each agent operates in its own thread (conversation context). Threads are connected through structured handoffs.

| Agent | Thread ID | Reads From |
|-------|-----------|-----------|
| CEO | 1 | Client |
| PM | 3 | Thread 1, Thread 7 |
| Designer | 4 | Thread 1, Thread 3 |
| Developer | 6 | Thread 1, Thread 3, Thread 4 |
| Researcher | 7 | Thread 1 |
| QA | 8 | Thread 1, Thread 3, Thread 6 |

[View Full Thread Guide →](templates/thread-architecture.md)

---

## Examples

### Complete Project Workflow
See how a restaurant website project flows through all 6 agents, from client request to deployment.

[View Project Example →](examples/client-project-example.md)

### Agent Handoff Patterns
Learn the exact format for passing work between agents with structured handoffs.

[View Handoff Example →](examples/agent-handoff-example.md)

---

## Shared Rules

The shared rules ensure all agents work together coherently:

1. **Read Before Write** — Always read relevant threads before starting
2. **Respect Boundaries** — Stay in your lane, never overwrite others
3. **No Invention** — Don't create missing information, request it
4. **Structured Output** — Keep outputs clean for the next agent
5. **Source of Truth** — Treat other agents' documents as authoritative

[View Full Rules →](prompts/shared-rules.md)

---

## Contributing

Contributions are welcome! Feel free to:

- Add new agent roles
- Improve existing prompts
- Add setup guides for new platforms
- Share your workflow examples

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Inspired by multi-agent frameworks: CrewAI, LangGraph, AutoGen
- System prompt patterns from [awesome-ai-system-prompts](https://github.com/dontriskit/awesome-ai-system-prompts)
- Built with love for the AI agent community

---

<p align="center">
  <strong>Built by <a href="https://github.com/malvinjauhari">Malvin Jauhari</a></strong>
</p>
