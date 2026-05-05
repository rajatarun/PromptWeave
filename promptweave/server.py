"""FastMCP server exposing the normalize_prompt MCP tool."""

from __future__ import annotations

from fastmcp import FastMCP

from .intent_extractor import extract_intent
from .template_engine import TemplateEngine

mcp = FastMCP(
    name="PromptWeave",
    version="0.1.0",
    instructions=(
        "PromptWeave normalizes a raw user intent into model-optimized prompt variants "
        "for Claude, GPT-4, and Gemini. Call normalize_prompt before dispatching to any "
        "downstream model to maximize cross-model response consistency."
    ),
)

_engine = TemplateEngine()


@mcp.tool()
async def normalize_prompt(
    intent: str,
    target_models: list[str],
    constraints: dict = {},
) -> dict:
    """
    Normalize a natural language intent into model-optimized prompt variants.

    Args:
        intent: Raw natural language description of the task.
        target_models: Models to generate prompts for. Accepted values: "claude", "gpt4", "gemini".
        constraints: Optional field overrides applied after intent extraction,
                     e.g. {"tone": "formal", "format": "bullet_points"}.

    Returns:
        Dict mapping each requested model name to its rendered prompt string.
    """
    intent_json = await extract_intent(intent)

    # Apply caller overrides (only recognised intent fields are honoured)
    _INTENT_FIELDS = {"task", "audience", "tone", "format", "length", "constraints", "domain"}
    for key, value in constraints.items():
        if key in _INTENT_FIELDS:
            intent_json[key] = value

    results: dict[str, str] = {}
    for model in target_models:
        results[model] = _engine.render(model, intent_json)

    return results
