"""Few-shot intent extractor using Claude Haiku."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic

# Default field values used when Haiku omits or returns invalid data
_DEFAULTS: dict[str, Any] = {
    "task": "analyze",
    "audience": "general",
    "tone": "neutral",
    "format": "paragraph",
    "length": "medium",
    "constraints": [],
    "domain": "general",
}

_REQUIRED_FIELDS = set(_DEFAULTS.keys())

_SYSTEM_PROMPT = """\
You are an intent parser for a prompt normalization system. \
Given a natural language user request, extract structured intent information \
and return ONLY valid JSON matching the schema below. \
No explanation, no markdown fences, no commentary — just the JSON object.

Schema:
{
  "task":        string,  // one of: summarize, classify, extract, generate, compare, analyze, explain, translate, rewrite, review, answer, other
  "audience":    string,  // one of: executive, technical, general, student, expert, developer, legal, medical, other
  "tone":        string,  // one of: formal, casual, technical, friendly, professional, neutral, persuasive, academic
  "format":      string,  // one of: bullet_points, paragraph, numbered_list, table, json, markdown, code, prose, other
  "length":      string,  // one of: short, medium, long, detailed
  "constraints": array,   // list of specific requirements or restrictions (strings)
  "domain":      string   // one of: finance, legal, technical, creative, medical, education, business, science, general, other
}"""

_FEW_SHOT_EXAMPLES = [
    (
        "Summarize this earnings report for our CEO in 3 bullet points. No jargon, keep it under 100 words.",
        '{"task":"summarize","audience":"executive","tone":"formal","format":"bullet_points","length":"short","constraints":["no jargon","max 100 words","max 3 points"],"domain":"finance"}',
    ),
    (
        "Write a friendly explanation of how neural networks work for a high school student.",
        '{"task":"explain","audience":"student","tone":"friendly","format":"paragraph","length":"medium","constraints":[],"domain":"technical"}',
    ),
    (
        "Extract all action items from this meeting transcript and put them in a numbered list.",
        '{"task":"extract","audience":"general","tone":"neutral","format":"numbered_list","length":"short","constraints":["action items only"],"domain":"business"}',
    ),
    (
        "Compare the pros and cons of React vs Vue for a team of experienced frontend developers.",
        '{"task":"compare","audience":"developer","tone":"technical","format":"table","length":"medium","constraints":[],"domain":"technical"}',
    ),
    (
        "Generate a formal legal disclaimer for a SaaS product. Keep it comprehensive and cover liability.",
        '{"task":"generate","audience":"legal","tone":"formal","format":"paragraph","length":"detailed","constraints":["comprehensive","cover liability"],"domain":"legal"}',
    ),
    (
        "Rewrite this patient intake form in plain language that anyone can understand.",
        '{"task":"rewrite","audience":"general","tone":"friendly","format":"prose","length":"medium","constraints":["plain language","universally understandable"],"domain":"medical"}',
    ),
]


def _build_messages(user_input: str) -> list[dict]:
    messages: list[dict] = []
    for user_text, assistant_json in _FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": assistant_json})
    messages.append({"role": "user", "content": user_input})
    return messages


def _parse_response(raw: str) -> dict[str, Any]:
    """Extract JSON from the model response, tolerating minor formatting noise."""
    raw = raw.strip()
    # Strip markdown code fences if the model ignored instructions
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    # Find the outermost JSON object
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return {}
    return json.loads(raw[start:end])


def _merge_defaults(parsed: dict[str, Any]) -> dict[str, Any]:
    result = dict(_DEFAULTS)
    for field in _REQUIRED_FIELDS:
        if field in parsed and parsed[field] is not None:
            result[field] = parsed[field]
    # Ensure constraints is always a list
    if not isinstance(result["constraints"], list):
        result["constraints"] = [str(result["constraints"])]
    return result


def _make_client() -> anthropic.Anthropic | anthropic.AnthropicBedrock:
    if os.getenv("ANTHROPIC_API_KEY"):
        return anthropic.Anthropic()
    return anthropic.AnthropicBedrock()


def _model_id() -> str:
    return os.getenv("INTENT_MODEL_ID", "claude-haiku-4-5-20251001")


async def extract_intent(user_input: str) -> dict[str, Any]:
    """
    Parse raw user input into a structured intent dict via a few-shot Haiku call.
    Falls back to defaults for any field the model omits or returns invalid.
    """
    client = _make_client()
    response = client.messages.create(
        model=_model_id(),
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=_build_messages(user_input),
    )
    raw = response.content[0].text
    try:
        parsed = _parse_response(raw)
    except (json.JSONDecodeError, ValueError):
        parsed = {}
    return _merge_defaults(parsed)
