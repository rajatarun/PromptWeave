"""Integration tests for the normalize_prompt MCP tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from promptweave.server import normalize_prompt


def _mock_intent(overrides: dict = {}) -> dict:
    base = {
        "task": "summarize",
        "audience": "executive",
        "tone": "formal",
        "format": "bullet_points",
        "length": "short",
        "constraints": ["no jargon"],
        "domain": "finance",
    }
    base.update(overrides)
    return base


def _patch_extractor(intent: dict):
    """Return a context manager that patches extract_intent to return `intent`."""
    import asyncio

    async def _fake_extract(user_input: str) -> dict:
        return intent

    return patch("promptweave.server.extract_intent", side_effect=_fake_extract)


class TestNormalizePrompt:
    @pytest.mark.asyncio
    async def test_returns_prompts_for_all_requested_models(self):
        with _patch_extractor(_mock_intent()):
            result = await normalize_prompt(
                intent="Summarize this report for our CEO.",
                target_models=["claude", "gpt4", "gemini"],
            )
        assert set(result.keys()) == {"claude", "gpt4", "gemini"}

    @pytest.mark.asyncio
    async def test_returns_only_requested_models(self):
        with _patch_extractor(_mock_intent()):
            result = await normalize_prompt(
                intent="Explain quantum computing.",
                target_models=["claude"],
            )
        assert list(result.keys()) == ["claude"]

    @pytest.mark.asyncio
    async def test_claude_output_contains_xml_tags(self):
        with _patch_extractor(_mock_intent()):
            result = await normalize_prompt(
                intent="Summarize for executives.",
                target_models=["claude"],
            )
        assert "<role>" in result["claude"]
        assert "<task>" in result["claude"]

    @pytest.mark.asyncio
    async def test_gpt4_output_starts_with_role_prime(self):
        with _patch_extractor(_mock_intent()):
            result = await normalize_prompt(
                intent="Analyze this data.",
                target_models=["gpt4"],
            )
        assert result["gpt4"].startswith("You are a")

    @pytest.mark.asyncio
    async def test_gemini_output_is_conversational(self):
        with _patch_extractor(_mock_intent()):
            result = await normalize_prompt(
                intent="Write a summary.",
                target_models=["gemini"],
            )
        assert result["gemini"].startswith("Please")

    @pytest.mark.asyncio
    async def test_constraint_overrides_applied(self):
        with _patch_extractor(_mock_intent({"tone": "casual"})):
            result = await normalize_prompt(
                intent="Explain this concept.",
                target_models=["gpt4"],
                constraints={"tone": "formal", "length": "detailed"},
            )
        # The override should have changed tone to formal
        assert "formal" in result["gpt4"]

    @pytest.mark.asyncio
    async def test_unknown_constraint_keys_ignored(self):
        with _patch_extractor(_mock_intent()):
            result = await normalize_prompt(
                intent="Generate a report.",
                target_models=["claude"],
                constraints={"unknown_field": "value", "tone": "casual"},
            )
        # Should not raise; unknown_field is silently dropped
        assert "claude" in result

    @pytest.mark.asyncio
    async def test_empty_target_models_returns_empty_dict(self):
        with _patch_extractor(_mock_intent()):
            result = await normalize_prompt(
                intent="Do something.",
                target_models=[],
            )
        assert result == {}
