# Extending PromptWeave (planned)

> **Status:** Extension points are **not coded on `main` yet**. This document describes the intended format so contributors can align early work.

## Template packs (planned)

Templates will live as files (e.g. Jinja2) per target model profile:

```
templates/
  claude.j2
  gpt4.j2
  gemini.j2
```

**Contract (planned):**

- Input: validated intent dict (schema TBD in `promptweave/intent.py`).
- Output: UTF-8 string prompt for that model.
- Templates must not execute network calls.

## Registering a new model profile (planned)

1. Add `templates/<profile>.j2`.
2. Register profile metadata (display name, style notes) in a manifest YAML.
3. Add golden tests under `tests/fixtures/<profile>/`.

## MCP tool versioning (planned)

Breaking changes to tool input/output JSON will bump a `tool_version` field in server responses.

## What not to extend here

- Provider-specific authentication (belongs in the host agent or SDK).
- Arbitrary code execution inside templates (will be discouraged; lint in CI).

See [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) for first implementation tasks.
