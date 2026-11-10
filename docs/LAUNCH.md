# Launch draft (not published)

Use when Phase 1–2 ship. **Do not publish** until core features and tests exist on `main`.

## Draft post

**Title:** PromptWeave — one intent, many model-native prompts

**Problem:** Teams routing the same user request to Claude, GPT, and Gemini often maintain three prompt variants by hand. Drift causes inconsistent behavior and review overhead.

**Why it matters:** Agent systems increasingly use multiple models (cost, capability, fallback). Prompt format preferences differ (tags vs markdown vs conversational). A small normalization layer reduces duplication.

**What PromptWeave does (when implemented):**

- Accept structured or natural-language **intent**
- Render **per-model** prompt strings from shared templates
- Expose an optional **MCP tool** for agent runtimes

**Honest limits today:** `main` is scaffolding only — no renderer, no MCP server, no cloud deploy in this branch.

**Ask:** Try the quickstart, open issues for your framework (MCP, LangGraph, etc.), contribute templates.

## Communities (potential fit)

- MCP ecosystem discussions and tool registries
- LangChain / LangGraph contributor channels
- Local-first / self-hosted AI ops communities
- Python packaging and testing circles (early contributors)

## Checklist before real launch

- [ ] README quickstart runs on a clean machine (verified in CI)
- [ ] At least one offline integration test for templates
- [ ] SECURITY.md and threat notes reviewed
- [ ] Demo GIF or short screen recording (optional)
- [ ] No exaggerated claims in README
