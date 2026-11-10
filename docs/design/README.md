# Design notes

## Intent (planned)

A single **intent** object is the source of truth. Downstream prompts are derived views, not separately authored documents.

```
User text or API JSON
        │
        ▼
  Intent validation (local)
        │
        ▼
  Template render (per model profile)
        │
        ▼
  Map[str, str]  model_id -> prompt
```

## Deployment modes (planned)

| Mode | Cloud account | Notes |
|------|---------------|-------|
| Library-only | No | Render from fixtures; tests offline |
| Local MCP server | No | Default bind localhost |
| Optional remote templates | Maybe | Object storage; credentials via env |
| Optional LLM intent parse | Maybe | Sends user text to provider; opt-in |

## Related docs

- [security-notes.md](../security-notes.md)
- [EXTENDING.md](../EXTENDING.md)
