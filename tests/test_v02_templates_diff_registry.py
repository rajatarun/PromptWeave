"""Comprehensive tests for PromptWeave v0.2: templates, diff, registry, and CLI."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from promptweave import (
    PROMPT_ARTIFACT_SCHEMA,
    ContextBlock,
    IntentSpec,
    PromptDiff,
    PromptRegistry,
    UnresolvedVariableError,
    __version__,
    bind_variables,
    compile_prompt,
    diff_compiled,
)
from promptweave.cli import main as cli_main


def _template_spec() -> IntentSpec:
    return IntentSpec(
        name="incident_responder",
        role="On-call {{team}} SRE for {{service}}",
        task="Investigate alert {{alert_id}} on {{service}} and propose remediation.",
        constraints=[
            "Follow {{team}} runbook standards.",
            "Keep summary under {{max_words}} words.",
        ],
        context_blocks=[
            ContextBlock(
                label="alert_meta",
                content="Service={{ service }}, Region={{region}}, Alert={{alert_id}}",
                priority=10,
            ),
            ContextBlock(
                label="static_note",
                content="No placeholders here.",
                priority=5,
            ),
        ],
    )


def test_version_is_at_least_0_2_0():
    parts = tuple(int(p) for p in __version__.split(".")[:3])
    assert parts >= (0, 2, 0)


def test_bind_variables_substitutes_all_fields_without_mutating_original():
    original = _template_spec()
    original_snapshot = original.to_dict()

    bound = bind_variables(
        original,
        {
            "team": "Payments",
            "service": "checkout-api",
            "alert_id": "ALRT-42",
            "max_words": "120",
            "region": "us-east-1",
        },
        strict=True,
    )

    assert bound is not original
    assert original.to_dict() == original_snapshot
    assert bound.role == "On-call Payments SRE for checkout-api"
    assert bound.task == "Investigate alert ALRT-42 on checkout-api and propose remediation."
    assert bound.constraints == (
        "Follow Payments runbook standards.",
        "Keep summary under 120 words.",
    )
    assert bound.context_blocks[0].label == "alert_meta"
    assert bound.context_blocks[0].priority == 10
    assert (
        bound.context_blocks[0].content
        == "Service=checkout-api, Region=us-east-1, Alert=ALRT-42"
    )
    assert bound.context_blocks[1].content == "No placeholders here."


def test_bind_variables_strict_raises_listing_all_missing():
    spec = _template_spec()

    with pytest.raises(UnresolvedVariableError) as exc_info:
        bind_variables(spec, {"team": "Core", "service": "gateway"}, strict=True)

    err = exc_info.value
    assert isinstance(err, ValueError)
    assert err.missing == ("alert_id", "max_words", "region")
    msg = str(err)
    for var in ("alert_id", "max_words", "region"):
        assert var in msg


def test_bind_variables_non_strict_leaves_unresolved_intact():
    spec = _template_spec()
    bound = bind_variables(spec, {"team": "Core"}, strict=False)

    assert bound.role == "On-call Core SRE for {{service}}"
    assert "{{alert_id}}" in bound.task
    assert bound.constraints[0] == "Follow Core runbook standards."
    assert "{{max_words}}" in bound.constraints[1]
    assert "{{region}}" in bound.context_blocks[0].content


def test_diff_compiled_identical_prompts_zero_delta():
    spec = IntentSpec(
        name="summarize",
        role="Concise technical writer",
        task="Summarize the changelog.",
        constraints=["Use bullet points."],
    )
    c1 = compile_prompt(spec, family="claude")
    c2 = compile_prompt(spec, family="claude")

    diff = diff_compiled(c1, c2)
    assert isinstance(diff, PromptDiff)
    assert diff.changed is False
    assert diff.sha256_changed is False
    assert diff.token_delta == 0
    assert diff.family_changed is False
    assert diff.unified_system_diff == ""
    assert diff.unified_user_diff == ""

    payload = diff.to_dict()
    assert payload["changed"] is False
    assert payload["token_delta"] == 0
    assert json.loads(json.dumps(payload)) == payload


def test_diff_compiled_detects_content_token_and_family_changes():
    spec_a = IntentSpec(
        name="summarize",
        role="Technical writer",
        task="Summarize the changelog.",
        constraints=["Use bullet points."],
    )
    spec_b = IntentSpec(
        name="summarize",
        role="Principal Staff Technical Writer",
        task="Summarize the changelog and highlight all breaking API migrations in detail.",
        constraints=["Use bullet points.", "Include rollback guidance for every migration."],
    )

    compiled_a = compile_prompt(spec_a, family="openai_compat")
    compiled_b = compile_prompt(spec_b, family="openai_compat")
    diff = diff_compiled(compiled_a, compiled_b)

    assert diff.changed is True
    assert diff.sha256_changed is True
    assert diff.family_changed is False
    assert diff.token_delta > 0
    assert diff.token_delta == compiled_b.estimated_tokens - compiled_a.estimated_tokens
    assert "Principal Staff Technical Writer" in diff.unified_system_diff
    assert "breaking API migrations" in diff.unified_user_diff

    compiled_claude = compile_prompt(spec_a, family="claude")
    fam_diff = diff_compiled(compiled_a, compiled_claude)
    assert fam_diff.changed is True
    assert fam_diff.sha256_changed is True
    assert fam_diff.family_changed is True


def test_prompt_registry_roundtrip_wal_and_tamper_detection(tmp_path: Path):
    db_path = tmp_path / "registry.db"
    spec_v1 = IntentSpec(
        name="My Assistant Prompt",
        role="Helpful edge assistant",
        task="Answer user questions locally.",
    )
    spec_v2 = IntentSpec(
        name="My Assistant Prompt",
        role="Helpful edge assistant",
        task="Answer user questions locally and cite memory sources.",
    )
    other_spec = IntentSpec(
        name="other_prompt",
        task="Classify sensor telemetry.",
    )

    c1 = compile_prompt(spec_v1, family="local_small")
    c2 = compile_prompt(spec_v2, family="local_small")
    c_other = compile_prompt(other_spec, family="gemini")

    with PromptRegistry(db_path) as reg:
        art1 = reg.register(c1)
        art2 = reg.register(c2)
        reg.register(c_other)

        expected_keys = {
            "schema",
            "prompt_id",
            "name",
            "family",
            "sha256",
            "estimated_tokens",
            "system_prompt",
            "user_prompt",
            "created_at",
        }
        assert set(art1.keys()) == expected_keys
        assert art1["schema"] == PROMPT_ARTIFACT_SCHEMA == "prompt-artifact-v1"
        assert art1["prompt_id"] == c1.prompt_id
        assert art1["name"] == "My Assistant Prompt"
        assert art1["family"] == "local_small"
        assert art1["sha256"] == c1.sha256
        assert art1["estimated_tokens"] == c1.estimated_tokens
        assert art1["system_prompt"] == c1.system
        assert art1["user_prompt"] == c1.user
        assert art1["created_at"]

        # Re-registering same prompt_id is idempotent
        art1_again = reg.register(c1)
        assert art1_again["created_at"] == art1["created_at"]

    # Verify WAL mode and persistence across reopen
    conn = sqlite3.connect(str(db_path))
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
    finally:
        conn.close()

    with PromptRegistry(db_path) as reg2:
        fetched = reg2.get(c1.prompt_id)
        assert fetched == art1
        assert reg2.get("prompt:nonexistent@sha256:" + "0" * 64) is None

        versions = reg2.list_versions("My Assistant Prompt")
        assert len(versions) == 2
        assert {v["prompt_id"] for v in versions} == {c1.prompt_id, c2.prompt_id}
        assert versions[0]["prompt_id"] == art2["prompt_id"]

        all_versions = reg2.list_versions()
        assert len(all_versions) == 3

        assert reg2.verify(c1.prompt_id) is True
        assert reg2.verify(c2.prompt_id) is True
        assert reg2.verify("prompt:missing@sha256:" + "0" * 64) is False

    # Tamper with stored system_prompt directly in SQLite and verify detection
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE prompt_artifacts SET system_prompt = 'INJECTED SYSTEM' WHERE prompt_id = ?",
            (c1.prompt_id,),
        )
        conn.commit()
    finally:
        conn.close()

    with PromptRegistry(db_path) as reg3:
        assert reg3.verify(c1.prompt_id) is False
        assert reg3.verify(c2.prompt_id) is True


def test_cli_diff_and_registry_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    spec_a_path = tmp_path / "spec_a.json"
    spec_b_path = tmp_path / "spec_b.json"
    db_path = tmp_path / "prompts.db"

    spec_a_path.write_text(
        json.dumps(
            {
                "name": "triage",
                "role": "Triage bot",
                "task": "Classify ticket severity.",
            }
        ),
        encoding="utf-8",
    )
    spec_b_path.write_text(
        json.dumps(
            {
                "name": "triage",
                "role": "Senior Triage bot",
                "task": "Classify ticket severity and assign owner.",
            }
        ),
        encoding="utf-8",
    )

    # CLI diff --json
    rc = cli_main(["diff", str(spec_a_path), str(spec_b_path), "--family", "claude", "--json"])
    assert rc == 0
    diff_out = json.loads(capsys.readouterr().out)
    assert diff_out["changed"] is True
    assert diff_out["sha256_changed"] is True
    assert diff_out["token_delta"] > 0
    assert diff_out["family_changed"] is False

    # CLI registry register
    rc = cli_main(
        [
            "registry",
            "register",
            "--db",
            str(db_path),
            str(spec_a_path),
            "--family",
            "claude",
            "--json",
        ]
    )
    assert rc == 0
    reg_a = json.loads(capsys.readouterr().out)
    assert reg_a["schema"] == "prompt-artifact-v1"
    assert reg_a["name"] == "triage"

    rc = cli_main(
        [
            "registry",
            "register",
            "--db",
            str(db_path),
            str(spec_b_path),
            "--family",
            "claude",
            "--json",
        ]
    )
    assert rc == 0
    reg_b = json.loads(capsys.readouterr().out)
    assert reg_b["prompt_id"] != reg_a["prompt_id"]

    # CLI registry list
    rc = cli_main(["registry", "list", "--db", str(db_path), "--name", "triage", "--json"])
    assert rc == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed) == 2

    # CLI registry get
    rc = cli_main(["registry", "get", "--db", str(db_path), reg_a["prompt_id"], "--json"])
    assert rc == 0
    fetched = json.loads(capsys.readouterr().out)
    assert fetched["prompt_id"] == reg_a["prompt_id"]
    assert fetched["sha256"] == reg_a["sha256"]

    # CLI registry verify
    rc = cli_main(["registry", "verify", "--db", str(db_path), reg_a["prompt_id"], "--json"])
    assert rc == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["valid"] is True

    # CLI registry get missing returns 1
    rc = cli_main(["registry", "get", "--db", str(db_path), "prompt:missing@sha256:0000"])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err
