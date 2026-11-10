# Contributing to PromptWeave

Thank you for helping make PromptWeave easy to adopt. The project is **pre-alpha** on `main`; see [ROADMAP.md](ROADMAP.md) before large features.

## Development setup

```bash
git clone https://github.com/rajatarun/PromptWeave.git
cd PromptWeave
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

Requirements: **Python 3.10+**. No API keys needed for current tests.

## Tests

- Run: `pytest -v`
- Add tests under `tests/` mirroring package layout
- Prefer **offline** tests (no network) for core logic

## Style

- Python: follow existing module layout; type hints encouraged for public APIs
- Docs: keep claims aligned with code; mark **planned** features explicitly
- Commits: imperative subject line; reference issues when applicable

## Pull request process

1. Fork and branch from `main` (or use `cursor/<name>-9b25` for automated runs)
2. Keep PRs focused; link ROADMAP or issue
3. Ensure `pytest` passes locally (CI when added)
4. Update README / ROADMAP if behavior or install steps change

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Good first tasks

See [docs/GOOD_FIRST_ISSUES.md](docs/GOOD_FIRST_ISSUES.md).
