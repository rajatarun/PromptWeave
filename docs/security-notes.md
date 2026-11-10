# Security notes (threat model sketch)

**Scope:** Planned PromptWeave components handling user **intent** and generated **prompts**. Current `main` only installs a stub package.

## Assets

- User-provided natural language (may contain secrets or PII)
- Rendered prompts sent to downstream LLMs
- Template files (integrity matters; treat as code)

## Trust boundaries

| Boundary | Risk | Mitigation (planned) |
|----------|------|----------------------|
| User → PromptWeave input | Injection into templates | Strict intent schema; escape in Jinja; no `|safe` on user fields |
| PromptWeave → external LLM (optional) | Data exfiltration | Document opt-in; minimize fields sent; support local-only path |
| MCP network exposure | Unauthorized tool use | Bind localhost by default; auth left to host/gateway |
| Template supply chain | Malicious template | Review in PR; pin versions; CI diff on templates |

## What this project does **not** provide (planned)

- Authentication or per-call authorization tokens for tools (defer to host runtime)
- Encryption at rest for prompts (host responsibility)
- Formal compliance certifications

## Reporting

See [SECURITY.md](../SECURITY.md) for private disclosure.

## Supported versions

Security fixes target the latest **0.x** release on `main` once publishing begins. Until `0.1.0`, report issues against `main` directly.
