# PromptWeave

**Compose one user intent into model-aware prompts** — planned library and MCP surface for teams running multiple LLMs or agent frameworks.

PromptWeave is for **developers building agentic apps** who want consistent semantics across models without hand-maintaining separate prompt copies. The project is **early scaffolding only** on `main`; behavior described in examples and integration docs is **planned** unless explicitly marked implemented. See [ROADMAP.md](ROADMAP.md).

<!-- Demo GIF: add `docs/assets/demo.gif` after Phase 2 MCP demo is recorded. -->

## Quickstart (~5 minutes)

Requires Python 3.10+ and Git. No API keys or cloud accounts.

```bash
git clone https://github.com/rajatarun/PromptWeave.git
cd PromptWeave
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -v
```

You should see at least one passing test (`test_version_is_set`).

## Planned core workflow (examples)

These illustrate the **target** API; they are **not runnable** until Phase 1–2 land.

**1. Define intent (structured, model-neutral)**

```python
intent = {
    "task": "Summarize the quarterly report for an executive audience.",
    "tone": "formal",
    "format": "bullet_points",
    "constraints": {"max_words": 150},
}
```

**2. Render per-model prompts (planned)**

```python
# from promptweave import render_prompts  # planned
# prompts = render_prompts(intent, targets=["claude", "gpt4", "gemini"])
```

**3. Call from an MCP-capable agent (planned)**

```json
{
  "tool": "normalize_prompt",
  "arguments": {
    "intent": "Summarize Q3 for executives in bullet points, formal tone.",
    "target_models": ["claude", "gpt4"]
  }
}
```

Runnable walkthrough files live under [examples/](examples/).

## Local-first usage

Today, everything on `main` runs **offline**: install the package and run tests. Future optional features (remote template storage or cloud LLM calls for intent parsing) will be **opt-in** via configuration and documented in README when implemented.

## Documentation

| Doc | Purpose |
|-----|---------|
| [ROADMAP.md](ROADMAP.md) | What exists vs planned |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | Ecosystem adapters |
| [docs/EXTENDING.md](docs/EXTENDING.md) | Templates and plugins (planned) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup and PR process |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |

## License

Apache-2.0 — see [LICENSE](LICENSE).
