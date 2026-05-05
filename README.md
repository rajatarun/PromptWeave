# PromptWeave

MCP-compatible prompt normalization service for multi-model agentic systems.

PromptWeave accepts a raw user intent and emits model-optimized prompt variants for **Claude**, **GPT-4**, and **Gemini** — ensuring semantic consistency across models with fundamentally different prompt sensitivities.

Part of the [AIWeave](https://aiweave.org) ecosystem.

---

## How it works

```
User Natural Language Intent
        │
 [ Intent Extractor ]  ← few-shot Claude Haiku call
        │  returns: intent JSON
 [ Jinja2 Template Engine ]
   /          │          \
claude      gpt-4      gemini
```

1. **Intent Extractor** — A few-shot prompt sent to Claude Haiku parses the raw user input into a structured intent JSON object (task, audience, tone, format, length, constraints, domain).
2. **Template Engine** — One Jinja2 template per model renders the intent into each model's preferred prompt style (XML tags for Claude, role-primed markdown for GPT-4, conversational prose for Gemini).
3. **MCP Tool** — `normalize_prompt` is exposed as a single MCP tool callable by any agent before dispatching to a downstream model.

## MCP Tool

```python
normalize_prompt(
    intent: str,              # raw user input
    target_models: list[str], # ["claude", "gpt4", "gemini"]
    constraints: dict = {}    # optional field overrides
) -> dict                     # {model: rendered_prompt, ...}
```

**Example response:**
```json
{
  "claude":  "<role>You are a formal finance assistant.</role><task>Summarize the following content.</task>...",
  "gpt4":    "You are a formal finance assistant.\n\nYour task: summarize the content below...",
  "gemini":  "Please summarize the following content in a formal way..."
}
```

## Local development

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Run the MCP server locally:

```bash
python app.py
# MCP endpoint: http://localhost:8000/mcp
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Set to use the Anthropic API directly. If unset, Bedrock is used. |
| `INTENT_MODEL_ID` | `claude-haiku-4-5-20251001` (API) / `anthropic.claude-haiku-4-5-20251001-v1:0` (Bedrock) | Model used for intent extraction |
| `TEMPLATE_STORAGE` | `local` | `local` or `s3` |
| `TEMPLATE_BUCKET` | — | S3 bucket name (required when `TEMPLATE_STORAGE=s3`) |
| `PORT` | `8000` | Local server port |

## Deployment (AWS Lambda + SAM)

```bash
sam build --use-container
sam deploy --guided
```

CI/CD via GitHub Actions OIDC — see `.github/workflows/deploy.yml`. Requires:
- `AWS_ACCOUNT_ID` secret
- `TEMPLATE_BUCKET` secret
- IAM role `teamweave-github-actions-sam-deployer` with Bedrock and S3 permissions

## Templates

Templates live in `templates/` as versioned `.j2` files. When `TEMPLATE_STORAGE=s3`, they are fetched from S3 at runtime — update templates without redeploying Lambda.

| File | Model | Style |
|---|---|---|
| `claude.j2` | Claude | XML-structured (`<role>`, `<task>`, `<constraints>`, `<format>`) |
| `gpt4.j2` | GPT-4 | Role-primed markdown |
| `gemini.j2` | Gemini | Conversational prose |

---

*PromptWeave is an independent applied research project by [Tarun Raja](https://tarunraja.info). Not affiliated with or a deliverable of any employer.*
