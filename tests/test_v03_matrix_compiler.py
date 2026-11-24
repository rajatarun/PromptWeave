"""Unit tests for PromptWeave v0.3.0 multi-family matrix compiler and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import promptweave
from promptweave import (
    SUPPORTED_FAMILIES,
    ContextBlock,
    Example,
    IntentSpec,
    MatrixFamilyEntry,
    MatrixReport,
    UnresolvedVariableError,
    compile_matrix,
    compile_prompt,
)
from promptweave.cli import main as cli_main


def _sample_spec(**overrides) -> IntentSpec:
    base = {
        "name": "edge_triage",
        "role": "Concise Raspberry Pi triage assistant for {{env}}.",
        "task": "Summarize alert {{alert_id}} and recommend the safest local action.",
        "audience": "Home edge operator",
        "tone": "calm and direct",
        "constraints": (
            "Never exfiltrate personal data.",
            "Cite context labels in your answer.",
        ),
        "context_blocks": (
            ContextBlock(
                label="critical_sensor",
                content="CPU temperature is 78C on {{node_name}}.",
                priority=10,
            ),
            ContextBlock(
                label="background_log",
                content="Routine heartbeat nominal across peripheral bus. " * 25,
                priority=1,
            ),
        ),
        "examples": (
            Example(
                input="Temp 82C on pi-01",
                output="Throttle non-essential background jobs and verify fan RPM.",
            ),
        ),
    }
    base.update(overrides)
    return IntentSpec(**base)


def test_version_and_public_exports():
    assert promptweave.__version__ == "0.3.0"
    assert hasattr(promptweave, "compile_matrix")
    assert hasattr(promptweave, "MatrixReport")
    assert hasattr(promptweave, "MatrixFamilyEntry")


def test_compile_matrix_all_four_families_deterministic():
    spec = _sample_spec(
        role="Concise triage assistant.",
        task="Summarize the alert.",
        context_blocks=(
            ContextBlock(label="sensor", content="CPU temp 72C.", priority=10),
        ),
    )

    report_a = compile_matrix(spec)
    report_b = compile_matrix(spec)

    assert isinstance(report_a, MatrixReport)
    assert report_a.spec_name == "edge_triage"
    assert tuple(report_a.families.keys()) == SUPPORTED_FAMILIES
    assert len(report_a.families) == 4
    assert report_a.to_dict() == report_b.to_dict()

    for fam in SUPPORTED_FAMILIES:
        entry = report_a.families[fam]
        direct = compile_prompt(spec, family=fam)
        assert isinstance(entry, MatrixFamilyEntry)
        assert entry.family == fam
        assert entry.prompt_id == direct.prompt_id
        assert entry.sha256 == direct.sha256
        assert len(entry.sha256) == 64
        assert entry.estimated_tokens == direct.estimated_tokens
        assert entry.trimmed_blocks == tuple(direct.dropped_context_blocks)
        assert entry.compiled is not None
        assert entry.compiled.sha256 == direct.sha256

    # Distinct model-family renderers produce distinct digests
    digests = {entry.sha256 for entry in report_a.families.values()}
    assert len(digests) == 4


def test_compile_matrix_identifies_min_and_max_tokens_family():
    spec = _sample_spec(
        role="Edge agent",
        task="Evaluate sensor reading.",
        context_blocks=(
            ContextBlock(label="fact", content="Voltage 5.1V", priority=10),
        ),
    )
    report = compile_matrix(spec)

    token_counts = {fam: entry.estimated_tokens for fam, entry in report.families.items()}
    assert token_counts[report.min_tokens_family] == min(token_counts.values())
    assert token_counts[report.max_tokens_family] == max(token_counts.values())

    payload = report.to_dict()
    assert payload["min_tokens_family"] == report.min_tokens_family
    assert payload["max_tokens_family"] == report.max_tokens_family
    assert set(payload["families"].keys()) == set(SUPPORTED_FAMILIES)
    for fam, item in payload["families"].items():
        assert set(item.keys()) == {
            "family",
            "prompt_id",
            "sha256",
            "estimated_tokens",
            "trimmed_blocks",
        }
        assert item["family"] == fam


def test_compile_matrix_binds_variables_before_compilation():
    spec = _sample_spec()
    variables = {
        "env": "kitchen-pi",
        "alert_id": "ALRT-42",
        "node_name": "pi5-edge-01",
    }

    report = compile_matrix(spec, variables=variables)
    assert report.variables_bound == variables
    assert report.to_dict()["variables_bound"] == variables

    # Original spec must remain unmutated
    assert "{{env}}" in (spec.role or "")
    assert "{{alert_id}}" in spec.task

    for entry in report.families.values():
        assert entry.compiled is not None
        rendered = entry.compiled.rendered
        assert "kitchen-pi" in rendered
        assert "ALRT-42" in rendered
        assert "pi5-edge-01" in rendered
        assert "{{" not in rendered


def test_compile_matrix_missing_variable_raises():
    spec = _sample_spec()
    with pytest.raises(UnresolvedVariableError) as exc_info:
        compile_matrix(spec, variables={"env": "kitchen-pi"})
    assert "alert_id" in exc_info.value.missing
    assert "node_name" in exc_info.value.missing


def test_compile_matrix_family_subset_and_aliases():
    spec = _sample_spec(
        role="Helper",
        task="Check status.",
        context_blocks=(),
    )
    report = compile_matrix(
        spec,
        families=["anthropic", "llama_local", "claude", "gemini"],
    )
    # Aliases canonicalize and deduplicate preserving first-seen order
    assert list(report.families.keys()) == ["claude", "local_small", "gemini"]
    assert report.min_tokens_family in report.families
    assert report.max_tokens_family in report.families


def test_compile_matrix_invalid_families_rejected():
    spec = _sample_spec(role="Helper", task="Ping", context_blocks=())
    with pytest.raises(ValueError, match="at least one"):
        compile_matrix(spec, families=[])
    with pytest.raises(ValueError, match="Unsupported model family"):
        compile_matrix(spec, families=["unknown_llm"])


def test_compile_matrix_respects_max_tokens_and_reports_trimmed_blocks():
    spec = _sample_spec(
        role="Helper",
        task="Inspect sensor.",
        context_blocks=(
            ContextBlock(label="critical", content="Temp 78C.", priority=10),
            ContextBlock(label="filler", content="Verbose narrative text. " * 60, priority=1),
        ),
        examples=(),
    )
    report = compile_matrix(spec, max_tokens=140)
    assert report.max_tokens == 140
    assert report.to_dict()["max_tokens"] == 140
    for entry in report.families.values():
        assert entry.estimated_tokens <= 140
        assert "filler" in entry.trimmed_blocks
        assert "critical" not in entry.trimmed_blocks


def test_cli_matrix_json_all_families_and_vars(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    spec_file = tmp_path / "matrix_spec.json"
    spec_file.write_text(
        json.dumps(
            {
                "name": "cli_matrix_demo",
                "role": "Edge assistant for {{zone}}",
                "task": "Report status for {{device}}.",
                "constraints": ["Be brief"],
                "context_blocks": [
                    {"label": "metric", "content": "Battery 91% on {{device}}.", "priority": 10},
                    {
                        "label": "noise",
                        "content": "Background telemetry line. " * 40,
                        "priority": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    rc = cli_main(
        [
            "matrix",
            str(spec_file),
            "--var",
            "zone=garage",
            "--var",
            "device=sensor-7",
            "--json",
        ]
    )
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["spec_name"] == "cli_matrix_demo"
    assert set(payload["families"].keys()) == set(SUPPORTED_FAMILIES)
    assert payload["variables_bound"] == {"zone": "garage", "device": "sensor-7"}
    assert payload["min_tokens_family"] in SUPPORTED_FAMILIES
    assert payload["max_tokens_family"] in SUPPORTED_FAMILIES
    for fam in SUPPORTED_FAMILIES:
        entry = payload["families"][fam]
        assert entry["prompt_id"].startswith("prompt:cli_matrix_demo@sha256:")
        assert len(entry["sha256"]) == 64
        assert entry["estimated_tokens"] > 0


def test_cli_matrix_subset_families_and_text_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    spec_file = tmp_path / "simple.json"
    spec_file.write_text(
        json.dumps({"name": "simple", "task": "Say hello."}),
        encoding="utf-8",
    )

    rc = cli_main(
        [
            "matrix",
            str(spec_file),
            "--families",
            "anthropic,openai_compat",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "spec: simple" in out
    assert "claude:" in out
    assert "openai_compat:" in out
    assert "min_tokens_family:" in out
    assert "max_tokens_family:" in out


def test_cli_matrix_error_cases(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    spec_file = tmp_path / "var_spec.json"
    spec_file.write_text(
        json.dumps({"name": "var_spec", "task": "Greet {{name}}."}),
        encoding="utf-8",
    )

    # Invalid --var format (missing '=')
    rc = cli_main(["matrix", str(spec_file), "--var", "badformat"])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err

    # Unknown family
    rc = cli_main(["matrix", str(spec_file), "--families", "nonexistent"])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err

    # Unresolved template variable
    rc = cli_main(["matrix", str(spec_file), "--var", "other=val"])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err
