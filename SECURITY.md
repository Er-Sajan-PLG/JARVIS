# Security Policy

**Status**: ACTIVE
**Type**: policy
**Last Updated**: 2026-09-19
**Source**: `githooks/pre-push`, `scripts/verify-push.sh`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `scripts/board/review.py` at HEAD

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.x     | :white_check_mark: |
| 2.x     | :x: (archived)     |
| < 2.0   | :x:                |

## Push shield (no branch protection available)

GitHub returns 403 for branch protection on private-free repos (TD-006),
so enforcement lives in three local layers. Broken code reaching remote
means all three failed — treat that as an incident, not a nuisance.

| Layer | Mechanism | Blocks on |
|---|---|---|
| Commit | pre-commit: gitleaks, ruff, commitlint | secrets, lint, message format |
| Push | `githooks/pre-push` (blocking, no bypass) | force-push, branch/tag deletion, unsigned commits, gitleaks range, ruff, doc gates, full unit suite |
| After | `scripts/verify-push.sh` (bypass detector) | unsigned commits, secrets in range, red remote CI |

Rules with no exceptions: every pushed commit is SSH-signed
(`commit.gpgsign`, ED25519); force-pushes and ref deletions are refused;
`--no-verify` is treated as hostile — `verify-push.sh` exists precisely to
catch it. To re-sign history after a rebase:
`git rebase --exec "git commit --amend --no-edit -S"`.

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
