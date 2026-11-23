"""Unit tests for PromptWeave deterministic compiler, adapters, and fingerprinting."""

from __future__ import annotations

import re

import pytest

from promptweave import (
    SUPPORTED_FAMILIES,
    ContextBlock,
    Example,
    IntentSpec,
    __version__,
    compile_prompt,
    estimate_tokens,
)


def _rich_spec(**overrides) -> IntentSpec:
    base = {
        "name": "triage_agent",
        "task": "Classify the incoming support ticket and recommend next steps.",
        "role": "Senior Support Triage Engineer",
        "audience": "on-call engineers",
        "tone": "concise and objective",
        "constraints": [
            "Never fabricate log timestamps.",
            "Output valid JSON only.",
        ],
        "output_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["severity", "summary"],
        },
        "context_blocks": [
            ContextBlock(label="sla_policy", content="P1 response SLA is 15 minutes.", priority=10),
            ContextBlock(
                label="recent_deploys",
                content="Deploy v2.14.0 rolled out to eu-west at 09:00 UTC.",
                priority=5,
            ),
            ContextBlock(
                label="chatter_log",
                content="General team chatter and unrelated background notes " * 12,
                priority=1,
            ),
        ],
        "examples": [
            Example(
                input="Database CPU at 99% and checkout failing.",
                output='{"severity": "P1", "summary": "Checkout outage due to DB CPU saturation"}',
            )
        ],
        "tools": [
            {
                "name": "lookup_incident",
                "description": "Fetch active incident metadata by service name.",
            }
        ],
    }
    base.update(overrides)
    return IntentSpec(**base)


def test_version_is_0_1_0():
    assert __version__ == "0.1.0"


@pytest.mark.parametrize("family", SUPPORTED_FAMILIES)
def test_all_four_model_families_render_distinctly(family: str):
    spec = _rich_spec()
    compiled = compile_prompt(spec, family=family)

    assert compiled.family == family
    assert re.fullmatch(r"prompt:triage_agent@sha256:[0-9a-f]{64}", compiled.prompt_id)
    assert compiled.prompt_id.endswith(compiled.sha256)
    assert compiled.estimated_tokens == estimate_tokens(compiled.rendered)
    assert compiled.estimated_tokens > 0
    assert compiled.dropped_context_blocks == []
    assert len(compiled.messages) == 2
    assert compiled.messages[0]["role"] == "system"
    assert compiled.messages[1]["role"] == "user"

    if family == "local_small":
        assert "### ROLE" in compiled.system
        assert "### RULES" in compiled.system
        assert "### TASK" in compiled.user
        assert "### END" in compiled.user
    elif family == "claude":
        assert "<role>" in compiled.system
        assert "<constraints>" in compiled.system
        assert "<context>" in compiled.user
        assert "<task>" in compiled.user
    elif family == "gemini":
        assert "## Role" in compiled.system
        assert "## Constraints" in compiled.system
        assert "## Context" in compiled.user
        assert "## Task" in compiled.user
    elif family == "openai_compat":
        assert "Role: Senior Support Triage Engineer" in compiled.system
        assert "Constraints:" in compiled.system
        assert "Task:\n" in compiled.user
        assert "[system]" in compiled.rendered
        assert "[user]" in compiled.rendered


def test_deterministic_sha256_across_repeated_compilations():
    spec_a = _rich_spec()
    spec_b = IntentSpec.from_dict(spec_a.to_dict())

    for family in SUPPORTED_FAMILIES:
        c1 = compile_prompt(spec_a, family=family)
        c2 = compile_prompt(spec_b, family=family)
        assert c1.sha256 == c2.sha256
        assert c1.prompt_id == c2.prompt_id
        assert c1.rendered == c2.rendered


def test_sha256_changes_on_constraint_mutation_and_family_change():
    base_spec = _rich_spec()
    mutated_spec = _rich_spec(
        constraints=[
            "Never fabricate log timestamps.",
            "Output valid JSON only.",
            "Always include root-cause hypothesis.",
        ]
    )

    c_base = compile_prompt(base_spec, family="claude")
    c_mutated = compile_prompt(mutated_spec, family="claude")
    c_other_family = compile_prompt(base_spec, family="gemini")

    assert c_base.sha256 != c_mutated.sha256
    assert c_base.prompt_id != c_mutated.prompt_id
    assert c_base.sha256 != c_other_family.sha256


def test_priority_based_context_trimming_under_max_tokens():
    spec = _rich_spec()
    full = compile_prompt(spec, family="local_small")

    # Pick a budget smaller than full prompt so low-priority chatter_log must be dropped,
    # while high-priority sla_policy is retained.
    budget = full.estimated_tokens - 40
    trimmed = compile_prompt(spec, family="local_small", max_tokens=budget)

    assert trimmed.estimated_tokens <= budget
    assert "chatter_log" in trimmed.dropped_context_blocks
    assert "sla_policy" not in trimmed.dropped_context_blocks
    assert "P1 response SLA is 15 minutes." in trimmed.user
    assert "General team chatter" not in trimmed.user
    assert trimmed.sha256 != full.sha256


def test_priority_tie_drops_later_block_first():
    spec = IntentSpec(
        name="tie_test",
        task="Summarize notes.",
        context_blocks=[
            ContextBlock(label="first_block", content="Alpha " * 30, priority=5),
            ContextBlock(label="second_block", content="Beta " * 30, priority=5),
        ],
    )
    full = compile_prompt(spec, family="openai_compat")
    trimmed = compile_prompt(spec, family="openai_compat", max_tokens=full.estimated_tokens - 20)

    assert trimmed.dropped_context_blocks == ["second_block"]
    assert "first_block" in trimmed.user
    assert "second_block" not in trimmed.user


def test_invalid_family_and_invalid_max_tokens_raise_value_error():
    spec = _rich_spec()

    with pytest.raises(ValueError, match="Unsupported model family"):
        compile_prompt(spec, family="unknown_model_v9")

    with pytest.raises(ValueError, match="max_tokens must be a positive integer"):
        compile_prompt(spec, family="claude", max_tokens=0)

    with pytest.raises(ValueError, match="task must be a non-empty string"):
        IntentSpec(task="   ")


def test_dict_constraints_and_format_alias_normalization():
    spec = IntentSpec.from_dict(
        {
            "task": "Explain PromptWeave.",
            "format": "short_paragraph",
            "constraints": {"avoid_hype": True, "max_words": 80},
        }
    )
    assert spec.output_schema == "short_paragraph"
    assert spec.constraints == ("avoid_hype", "max_words: 80")
    compiled = compile_prompt(spec, family="gemini")
    assert "## Output Format\nshort_paragraph" in compiled.system
    assert "* avoid_hype" in compiled.system
