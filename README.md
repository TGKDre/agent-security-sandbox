# Agent Security Sandbox

A controlled adversarial evaluation environment for tool-using LLM agents.
Companion project to [llm-redteam-harness](https://github.com/TGKDre/llm-redteam-harness).

## Threat Classes

| Threat | Description |
|---|---|
| Prompt Injection | Malicious instructions in retrieved documents override agent behavior |
| Secret Exfiltration | Agent leaks credentials/tokens via tool chains |
| Privilege Escalation | Social engineering the agent into requesting elevated access |
| Role Confusion | Injected content reassigns agent identity or instructions |

## Architecture

```
run_sandbox.py          Entry point
agents/tool_agent.py    LLM agent with tool-calling loop (OpenAI function calling)
tools/registry.py       Simulated tools: read_document, run_shell, lookup_user, send_message
scenarios/              YAML attack scenario definitions
judges/action_judge.py  Evaluates agent trace for compromise signals
reports/                JSON + Markdown evaluation output
```

## Quickstart

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python run_sandbox.py --scenario scenarios/ --model gpt-3.5-turbo
```

## Design

- All tools are sandboxed simulations with no real system access
- Secrets in the tool store are synthetic test values
- Injection payloads simulate real RAG + agent pipeline attacks
