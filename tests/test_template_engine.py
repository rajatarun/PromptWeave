"""Tests for the Jinja2 template engine."""

from __future__ import annotations

import pytest

from promptweave.template_engine import TemplateEngine

_FULL_INTENT = {
    "task": "summarize",
    "audience": "executive",
    "tone": "formal",
    "format": "bullet_points",
    "length": "short",
    "constraints": ["no jargon", "max 3 points"],
    "domain": "finance",
}

_MINIMAL_INTENT = {
    "task": "analyze",
    "audience": "general",
    "tone": "neutral",
    "format": "paragraph",
    "length": "medium",
    "constraints": [],
    "domain": "general",
}


@pytest.fixture(scope="module")
def engine():
    return TemplateEngine()


class TestClaudeTemplate:
    def test_contains_xml_role_tag(self, engine):
        output = engine.render("claude", _FULL_INTENT)
        assert "<role>" in output and "</role>" in output

    def test_contains_xml_task_tag(self, engine):
        output = engine.render("claude", _FULL_INTENT)
        assert "<task>" in output and "</task>" in output

    def test_task_is_capitalised(self, engine):
        output = engine.render("claude", _FULL_INTENT)
        assert "Summarize" in output

    def test_constraints_rendered_when_present(self, engine):
        output = engine.render("claude", _FULL_INTENT)
        assert "<constraints>" in output
        assert "no jargon" in output
        assert "max 3 points" in output

    def test_constraints_block_absent_when_empty(self, engine):
        output = engine.render("claude", _MINIMAL_INTENT)
        assert "<constraints>" not in output

    def test_domain_included_in_role(self, engine):
        output = engine.render("claude", _FULL_INTENT)
        assert "finance" in output

    def test_general_domain_omitted_from_role(self, engine):
        output = engine.render("claude", _MINIMAL_INTENT)
        # "general" domain should not appear in the role tag
        assert "general assistant" not in output

    def test_format_tag_present(self, engine):
        output = engine.render("claude", _FULL_INTENT)
        assert "<format>" in output
        assert "bullet points" in output  # underscore replaced


class TestGpt4Template:
    def test_contains_role_priming_line(self, engine):
        output = engine.render("gpt4", _FULL_INTENT)
        assert output.startswith("You are a")

    def test_task_in_output(self, engine):
        output = engine.render("gpt4", _FULL_INTENT)
        assert "summarize" in output.lower()

    def test_audience_in_output(self, engine):
        output = engine.render("gpt4", _FULL_INTENT)
        assert "executive" in output

    def test_constraints_joined_with_comma(self, engine):
        output = engine.render("gpt4", _FULL_INTENT)
        assert "no jargon, max 3 points" in output

    def test_no_rules_line_when_no_constraints(self, engine):
        output = engine.render("gpt4", _MINIMAL_INTENT)
        assert "Rules:" not in output

    def test_domain_included(self, engine):
        output = engine.render("gpt4", _FULL_INTENT)
        assert "finance" in output


class TestGeminiTemplate:
    def test_conversational_opening(self, engine):
        output = engine.render("gemini", _FULL_INTENT)
        assert output.startswith("Please")

    def test_task_in_output(self, engine):
        output = engine.render("gemini", _FULL_INTENT)
        assert "summarize" in output.lower()

    def test_tone_in_output(self, engine):
        output = engine.render("gemini", _FULL_INTENT)
        assert "formal" in output

    def test_constraints_joined_with_and(self, engine):
        output = engine.render("gemini", _FULL_INTENT)
        assert "no jargon and max 3 points" in output

    def test_no_also_line_when_no_constraints(self, engine):
        output = engine.render("gemini", _MINIMAL_INTENT)
        assert "Also:" not in output

    def test_format_underscores_replaced(self, engine):
        output = engine.render("gemini", _FULL_INTENT)
        assert "bullet points" in output
        assert "bullet_points" not in output


class TestTemplateEngineErrors:
    def test_unsupported_model_raises_value_error(self, engine):
        with pytest.raises(ValueError, match="Unsupported model"):
            engine.render("llama", _FULL_INTENT)
