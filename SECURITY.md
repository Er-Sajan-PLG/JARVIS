# Security Policy

**Status**: ACTIVE
**Type**: policy
**Last Updated**: 2026-09-13

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.x     | :white_check_mark: |
| 2.x     | :x: (archived)     |
| < 2.0   | :x:                |

## Reporting a Vulnerability

JARVIS is a **single-tenant, self-hosted** personal AI platform. Security
issues are still taken seriously.

**Please do NOT open a public issue for a vulnerability.**

Report vulnerabilities privately to the maintainer:

- GitHub: `Er-Sajan-PLG` (private security advisory via
  `Security → Advisories → New draft security advisory`)

### What to include

1. A description of the vulnerability and its impact.
2. Steps to reproduce (as minimal as possible).
3. Affected version(s).
4. Any suggested fix or mitigation.

### Response SLA

| Severity | First response | Resolution target |
|----------|----------------|-------------------|
| Critical | 48h            | 7 days            |
| High     | 72h            | 14 days           |
| Medium   | 1 week         | 30 days           |
| Low      | best effort    | next release      |

### Scope

Security-relevant surface area:

- `app/adapters/` — HTTP/WS auth (`validate_api_key`, Bearer/X-API-Key)
- `app/guardrails/` — `@safety_gate` tiered tool safety (SAFE/SENSITIVE/DESTRUCTIVE)
- `app/models/` — LLM provider clients & API key handling
- `.env` secret management
- Prompt injection / tool-call parsing (`app/tools/executor.py`)

Out of scope: the local Ollama/llama.cpp runtime, third-party LLM providers,
and the user's own machine.
