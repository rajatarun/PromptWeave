"""Tests for PromptWeave deterministic prompt lockfile and drift detector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptweave.cli import main as cli_main
from promptweave.compiler import compile_prompt
from promptweave.lockfile import LOCK_VERSION, generate_lockfile, verify_lockfile
from promptweave.registry import PromptRegistry
from promptweave.spec import IntentSpec


def _make_spec(name: str, task: str) -> IntentSpec:
    return IntentSpec(
        name=name,
        role="You are a concise local assistant.",
        task=task,
        constraints=("Be truthful.",),
    )


def test_generate_and_verify_clean_lockfile(tmp_path: Path) -> None:
    db = tmp_path / "reg.db"
    spec = _make_spec("summarize", "Summarize the input in two sentences.")
    with PromptRegistry(db) as reg:
        reg.register(compile_prompt(spec, family="claude"), name=spec.name)
        reg.register(compile_prompt(spec, family="openai_compat"), name=spec.name)

        lockfile = generate_lockfile(reg)
        assert lockfile["lock_version"] == LOCK_VERSION
        assert "summarize@v1:claude" in lockfile["entries"]
        assert "summarize@v1:openai_compat" in lockfile["entries"]
        assert lockfile["entries"]["summarize@v1:claude"]["token_estimate"] > 0

        report = verify_lockfile(reg, lockfile)
        assert report == {"passed": True, "drifted": [], "missing": [], "added": []}


def test_generate_lockfile_across_explicit_families(tmp_path: Path) -> None:
    db = tmp_path / "reg_multi.db"
    spec = _make_spec("classify", "Classify intent into support or billing.")
    with PromptRegistry(db) as reg:
        reg.register(compile_prompt(spec, family="openai_compat"), name=spec.name)
        lockfile = generate_lockfile(reg, families=["claude", "openai", "gemini", "local"])
        assert set(lockfile["entries"].keys()) == {
            "classify@v1:claude",
            "classify@v1:openai",
            "classify@v1:gemini",
            "classify@v1:local",
        }
        assert verify_lockfile(reg, lockfile)["passed"] is True


def test_drift_missing_and_added_detection(tmp_path: Path) -> None:
    db1 = tmp_path / "reg1.db"
    spec_a = _make_spec("greeting", "Say hello warmly.")
    spec_b = _make_spec("farewell", "Say goodbye politely.")
    with PromptRegistry(db1) as reg1:
        reg1.register(compile_prompt(spec_a, family="claude"), name=spec_a.name)
        reg1.register(compile_prompt(spec_b, family="claude"), name=spec_b.name)
        lockfile = generate_lockfile(reg1)

    # Second registry: modify greeting (drift), drop farewell (missing), add help (added).
    db2 = tmp_path / "reg2.db"
    spec_a_mod = _make_spec("greeting", "Say hello formally and concisely.")
    spec_c = _make_spec("help", "Explain available commands.")
    with PromptRegistry(db2) as reg2:
        reg2.register(compile_prompt(spec_a_mod, family="claude"), name=spec_a_mod.name)
        reg2.register(compile_prompt(spec_c, family="claude"), name=spec_c.name)

        report = verify_lockfile(reg2, lockfile)
        assert report["passed"] is False
        assert len(report["drifted"]) == 1
        assert report["drifted"][0]["key"] == "greeting@v1:claude"
        assert report["missing"] == ["farewell@v1:claude"]
        assert report["added"] == ["help@v1:claude"]


def test_cli_lock_and_verify_lock_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "cli_reg.db"
    spec = _make_spec("router", "Route the user query.")
    with PromptRegistry(db) as reg:
        reg.register(compile_prompt(spec, family="claude"), name=spec.name)

    lock_path = tmp_path / "prompts.lock.json"
    rc_lock = cli_main(["lock", "--db", str(db), "--out", str(lock_path)])
    assert rc_lock == 0
    assert lock_path.is_file()

    rc_ok = cli_main(["verify-lock", "--db", str(db), "--lockfile", str(lock_path), "--json"])
    assert rc_ok == 0
    ok_payload = json.loads(capsys.readouterr().out)
    assert ok_payload["passed"] is True

    # Adding a new version causes verify-lock to exit non-zero.
    spec_v2 = _make_spec("router", "Route the user query with strict JSON output.")
    with PromptRegistry(db) as reg:
        reg.register(compile_prompt(spec_v2, family="claude"), name=spec_v2.name)

    rc_fail = cli_main(["verify-lock", "--db", str(db), "--lockfile", str(lock_path), "--json"])
    assert rc_fail == 1
    fail_payload = json.loads(capsys.readouterr().out)
    assert fail_payload["passed"] is False
    assert fail_payload["added"] == ["router@v2:claude"]
