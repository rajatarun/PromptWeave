"""Tests for the intent extractor."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from promptweave.intent_extractor import (
    _merge_defaults,
    _parse_response,
    extract_intent,
)


class TestParseResponse:
    def test_clean_json(self):
        raw = '{"task":"summarize","audience":"executive"}'
        result = _parse_response(raw)
        assert result["task"] == "summarize"
        assert result["audience"] == "executive"

    def test_strips_markdown_fences(self):
        raw = '```json\n{"task":"explain"}\n```'
        result = _parse_response(raw)
        assert result["task"] == "explain"

    def test_strips_plain_fences(self):
        raw = "```\n{\"task\":\"generate\"}\n```"
        result = _parse_response(raw)
        assert result["task"] == "generate"

    def test_extra_whitespace(self):
        raw = '  \n  {"task":"extract"}  \n  '
        result = _parse_response(raw)
        assert result["task"] == "extract"

    def test_returns_empty_dict_on_no_json(self):
        result = _parse_response("Sorry, I cannot parse that.")
        assert result == {}


class TestMergeDefaults:
    def test_all_fields_present(self):
        parsed = {
            "task": "summarize",
            "audience": "executive",
            "tone": "formal",
            "format": "bullet_points",
            "length": "short",
            "constraints": ["no jargon"],
            "domain": "finance",
        }
        result = _merge_defaults(parsed)
        assert result == parsed

    def test_missing_fields_filled_with_defaults(self):
        result = _merge_defaults({"task": "classify"})
        assert result["task"] == "classify"
        assert result["audience"] == "general"
        assert result["tone"] == "neutral"
        assert result["constraints"] == []

    def test_empty_input_is_all_defaults(self):
        result = _merge_defaults({})
        assert result["task"] == "analyze"
        assert result["domain"] == "general"

    def test_constraints_coerced_to_list(self):
        result = _merge_defaults({"constraints": "no jargon"})
        assert result["constraints"] == ["no jargon"]

    def test_none_values_replaced_by_defaults(self):
        result = _merge_defaults({"task": None, "audience": "executive"})
        assert result["task"] == "analyze"
        assert result["audience"] == "executive"


class TestExtractIntent:
    def _make_mock_response(self, json_str: str) -> MagicMock:
        content_block = MagicMock()
        content_block.text = json_str
        response = MagicMock()
        response.content = [content_block]
        return response

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        payload = {
            "task": "summarize",
            "audience": "executive",
            "tone": "formal",
            "format": "bullet_points",
            "length": "short",
            "constraints": ["no jargon", "max 3 points"],
            "domain": "finance",
        }
        mock_response = self._make_mock_response(json.dumps(payload))

        with patch("promptweave.intent_extractor._make_client") as mock_client_factory:
            client = MagicMock()
            client.messages.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = await extract_intent("Summarize this earnings report for our CEO.")

        assert result["task"] == "summarize"
        assert result["audience"] == "executive"
        assert result["constraints"] == ["no jargon", "max 3 points"]

    @pytest.mark.asyncio
    async def test_partial_response_merged_with_defaults(self):
        mock_response = self._make_mock_response('{"task":"extract"}')

        with patch("promptweave.intent_extractor._make_client") as mock_client_factory:
            client = MagicMock()
            client.messages.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = await extract_intent("Extract key facts.")

        assert result["task"] == "extract"
        assert result["audience"] == "general"  # default
        assert result["constraints"] == []  # default

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back_to_defaults(self):
        mock_response = self._make_mock_response("I cannot parse this request.")

        with patch("promptweave.intent_extractor._make_client") as mock_client_factory:
            client = MagicMock()
            client.messages.create.return_value = mock_response
            mock_client_factory.return_value = client

            result = await extract_intent("Something ambiguous.")

        assert result["task"] == "analyze"
        assert result["domain"] == "general"

    @pytest.mark.asyncio
    async def test_uses_anthropic_client_when_api_key_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        payload = {"task": "analyze"}
        mock_response = self._make_mock_response(json.dumps(payload))

        with patch("promptweave.intent_extractor.anthropic.Anthropic") as MockAnthropicClass:
            client = MagicMock()
            client.messages.create.return_value = mock_response
            MockAnthropicClass.return_value = client

            with patch("promptweave.intent_extractor._make_client", return_value=client):
                result = await extract_intent("Analyze this document.")

        assert result["task"] == "analyze"
