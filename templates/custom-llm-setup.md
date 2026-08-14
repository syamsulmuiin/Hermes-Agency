# Custom LLM Setup Guide

## How to Implement Hermes Agency with Any LLM API

### Overview

This guide shows you how to implement the Hermes Agency system with any LLM provider (OpenAI, Anthropic, Google, Mistral, local models, etc.) using a simple Python wrapper.

### Step 1: Project Structure

```
hermes-agency/
├── prompts/                    # Copy from this repo
├── config.yaml                 # Agent configurations
├── agency.py                   # Main orchestrator
└── requirements.txt            # Dependencies
```

### Step 2: Configuration

Create `config.yaml`:

```yaml
agents:
  ceo:
    name: "CEO Agent"
    prompt_file: "prompts/01-ceo-agent.md"
    model: "gpt-4o"
    temperature: 0.7

  pm:
    name: "Project Manager"
    prompt_file: "prompts/02-project-manager-agent.md"
    model: "gpt-4o"
    temperature: 0.5

  researcher:
    name: "Researcher"
    prompt_file: "prompts/03-researcher-agent.md"
    model: "gpt-4o"
    temperature: 0.3

  developer:
    name: "Developer"
    prompt_file: "prompts/04-developer-agent.md"
    model: "gpt-4o"
    temperature: 0.2

  designer:
    name: "Designer"
    prompt_file: "prompts/05-designer-agent.md"
    model: "gpt-4o"
    temperature: 0.8

  qa:
    name: "QA"
    prompt_file: "prompts/06-qa-agent.md"
    model: "gpt-4o"
    temperature: 0.3

shared_rules_file: "prompts/shared-rules.md"
```

### Step 3: Python Implementation

```python
import yaml
from pathlib import Path
from openai import OpenAI  # Or any LLM client

class HermesAgency:
    def __init__(self, config_path="config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.client = OpenAI()  # Configure for your provider
        self.threads = {}  # Thread storage

    def load_prompt(self, agent_name):
        prompt_file = self.config["agents"][agent_name]["prompt_file"]
        shared_rules = self.config["shared_rules_file"]

        agent_prompt = Path(prompt_file).read_text()
        shared = Path(shared_rules).read_text()

        return f"{shared}\n\n---\n\n{agent_prompt}"

    def chat(self, agent_name, message, thread_id=None):
        if thread_id is None:
            thread_id = agent_name

        # Get or create thread history
        if thread_id not in self.threads:
            self.threads[thread_id] = []

        # Build messages
        system_prompt = self.load_prompt(agent_name)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.threads[thread_id])
        messages.append({"role": "user", "content": message})

        # Call LLM
        response = self.client.chat.completions.create(
            model=self.config["agents"][agent_name]["model"],
            messages=messages,
            temperature=self.config["agents"][agent_name]["temperature"]
        )

        assistant_message = response.choices[0].message.content

        # Store in thread
        self.threads[thread_id].append({"role": "user", "content": message})
        self.threads[thread_id].append({"role": "assistant", "content": assistant_message})

        return assistant_message

    def handoff(self, from_agent, to_agent, message):
        """Pass context from one agent to another."""
        return self.chat(to_agent, message)

# Usage
agency = HermesAgency()

# CEO talks to client
brief = agency.chat("ceo", "I need a restaurant website with ordering...")

# Pass to Researcher
research = agency.handoff("ceo", "researcher", brief)

# Pass to PM
plan = agency.handoff("ceo", "pm", f"{brief}\n\n{research}")
```

### Step 4: Supported Providers

| Provider | Client Library | Config Change |
|----------|---------------|---------------|
| OpenAI | `openai` | Default |
| Anthropic | `anthropic` | Change client class |
| Google | `google-generativeai` | Change client class |
| Mistral | `mistralai` | Change client class |
| Local (Ollama) | `openai` (compatible) | Set `base_url="http://localhost:11434/v1"` |
| AWS Bedrock | `boto3` | Use Bedrock runtime |

### Tips

- Start with temperature 0.7 for creative agents (CEO, Designer)
- Use temperature 0.2-0.3 for technical agents (Developer, QA)
- Store threads in a database for persistence
- Add logging to track agent interactions
