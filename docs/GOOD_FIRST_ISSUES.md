# Good first issues (draft for maintainers)

Copy these into GitHub issues. Acceptance criteria are scoped for `main` as it exists today plus the planned layout in [ROADMAP.md](../ROADMAP.md).

## 1. Add intent schema module

- **Files:** `promptweave/intent.py`, `tests/test_intent.py`
- **Scope:** `dataclass` or `TypedDict` for task, audience, tone, format, constraints; validation for required `task`.
- **Acceptance:** `pytest` passes; invalid input raises clear `ValueError`; no network.

## 2. Stub template renderer

- **Files:** `promptweave/template_engine.py`, `templates/README.md`, `tests/test_template_engine.py`
- **Scope:** Load a single static template string; render `sample_intent.json` fixture.
- **Acceptance:** One model profile (`claude` or `plain`) with golden expected output file.

## 3. CLI `promptweave --version`

- **Files:** `promptweave/cli.py`, `pyproject.toml` (`[project.scripts]`)
- **Scope:** Print `__version__` from package.
- **Acceptance:** `promptweave --version` works after `pip install -e .`.

## 4. GitHub Actions CI

- **Files:** `.github/workflows/ci.yml`
- **Scope:** Python 3.10–3.12 matrix; `pip install -e ".[dev]"`; `pytest`.
- **Acceptance:** Workflow runs on pull_request; badge optional in README.

## 5. Document template variable catalog

- **Files:** `docs/design/template-variables.md`
- **Scope:** List Jinja variables intended for all templates once engine exists.
- **Acceptance:** Linked from `docs/EXTENDING.md`.

## 6. Example: offline render script

- **Files:** `examples/render_offline.py`
- **Scope:** Read `examples/sample_intent.json`; print placeholder or real render when engine lands.
- **Acceptance:** Documented in `examples/README.md`; runs without API keys.

## 7. MCP server skeleton

- **Files:** `promptweave/mcp_server.py`, `tests/test_mcp_server.py`
- **Scope:** In-process tests only; no live port required in CI.
- **Acceptance:** Tool schema documented; returns `501` or clear “not implemented” until logic exists.

## 8. OpenTelemetry span helper (no-op default)

- **Files:** `promptweave/telemetry.py`, `tests/test_telemetry.py`
- **Scope:** Context manager that no-ops unless `OTEL_EXPORTER_OTLP_ENDPOINT` set.
- **Acceptance:** No mandatory OTel dependency until opted in.

## 9. LangGraph state adapter sketch

- **Files:** `docs/integrations/langgraph.md` + optional `examples/langgraph_stub.py`
- **Scope:** Document how `model_prompts` would attach to graph state.
- **Acceptance:** No false claims of working integration; marked “design only”.

## 10. SECURITY.md supported versions table

- **Files:** `SECURITY.md`
- **Scope:** Update supported version row when `0.1.0` is released.
- **Acceptance:** Matches latest git tag or `__version__`.
