# Integration opportunities

Status on `main`: **no integrations are implemented**. Ratings reflect fit for the **planned** PromptWeave shape: structured intent in, per-model prompts out, optional MCP tool.

| Ecosystem | Fit | Adapter sketch | Effort | Implemented today |
|-----------|-----|----------------|--------|-------------------|
| **MCP (servers & clients)** | **High** | Expose `normalize_prompt(intent, target_models[])` as an MCP tool; clients call before routing to downstream models. | M (2–3 weeks for MVP + tests) | No |
| **LangChain / LangGraph** | **High** | `Runnable` or graph node that accepts chain state + intent fields, writes `model_prompts` dict into state. | M | No |
| **OpenAI / Anthropic Python SDKs** | **Med** | Thin wrapper: after render, pass strings into `messages` for each provider; no SDK fork required. | S–M | No |
| **AWS Bedrock / AgentCore** | **Med** | Optional intent-extraction model on Bedrock; templates stay local. AgentCore: register as tool via Gateway. Requires AWS when enabled. | M–L | No |
| **OpenTelemetry** | **Med** | Span around intent parse + per-model render; attributes: `target_model`, template id, byte length (not prompt body by default). | S | No |
| **LiteLLM / unified routers** | **Med** | Pre-hook before `completion()` to swap in rendered system/user content per routed model. | S–M | No |
| **Vercel AI SDK / similar** | **Low** | UI-centric; value is mostly server-side unless exposing prompt preview in devtools. | S | No |
| **Haystack / LlamaIndex** | **Low–Med** | Pipeline component before query engine or agent planner. | M | No |

Effort key: **S** ≈ days, **M** ≈ 1–3 weeks, **L** ≈ month+ for production hardening.

## Top three to pursue first

1. **MCP** — matches agent-first adoption; single tool boundary; local server needs no cloud.
2. **LangGraph** — composes naturally with multi-model graphs and stateful agents.
3. **OpenTelemetry** — low effort, helps operators without changing core API.

## Honest limits

- Integrations that require sending user text to a remote LLM for intent parsing need clear **data handling** docs (see [security-notes.md](security-notes.md)).
- No integration should imply benchmarks, user counts, or production deployments that do not exist in this repo.
