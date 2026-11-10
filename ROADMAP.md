# Roadmap

This repository is **pre-alpha** on `main`: packaging and contributor docs exist; core runtime behavior is **not implemented yet**. Items below are planned unless marked done.

## Phase 0 — Foundation (in progress)

- [x] Apache-2.0 license
- [x] Installable Python package skeleton (`pip install -e ".[dev]"`)
- [x] Contributor and security documentation
- [x] CI workflow running `pytest` on pull requests

## Phase 1 — Core library (planned)

- Structured **intent** model (task, audience, tone, format, constraints)
- **Template engine** rendering one intent into model-specific prompt styles
- Pure-Python unit tests with **no network** required for core logic
- Golden-file fixtures for template output

## Phase 2 — MCP exposure (planned)

- MCP server exposing a `normalize_prompt`-style tool
- Local-first default: run on `localhost` without cloud accounts
- Optional cloud template storage (e.g. object storage) behind configuration

## Phase 3 — Integrations (planned)

See [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) for ecosystem fit and adapter sketches.

## Non-goals (for now)

- Hosted multi-tenant SaaS
- Built-in LLM routing or billing
- Storing end-user secrets in the repository

## How to influence priority

Open a discussion or issue describing your use case (MCP client, framework, or deployment target). See [docs/GOOD_FIRST_ISSUES.md](docs/GOOD_FIRST_ISSUES.md) for concrete starter tasks.
