"""Unit tests for the promptweave CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptweave.cli import main as cli_main


def test_cli_compile_json_output_and_trimming(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(
        json.dumps(
            {
                "name": "cli_demo",
                "role": "Helpful local assistant",
                "task": "Answer the user query using provided context.",
                "constraints": ["Be concise", "Cite context labels"],
                "context_blocks": [
                    {"label": "critical_fact", "content": "Port is 8080.", "priority": 10},
                    {
                        "label": "verbose_filler",
                        "content": "Unimportant historical narrative " * 30,
                        "priority": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    rc = cli_main(
        [
            "compile",
            str(spec_file),
            "--family",
            "claude",
            "--max-tokens",
            "120",
            "--json",
        ]
    )
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["family"] == "claude"
    assert payload["prompt_id"].startswith("prompt:cli_demo@sha256:")
    assert len(payload["sha256"]) == 64
    assert payload["estimated_tokens"] <= 120
    assert payload["dropped_context_blocks"] == ["verbose_filler"]
    assert "<task>" in payload["user"]
    assert "Port is 8080." in payload["user"]


def test_cli_compile_sample_intent_text_output(capsys: pytest.CaptureFixture[str]):
    sample_path = Path(__file__).resolve().parent.parent / "examples" / "sample_intent.json"
    rc = cli_main(["compile", str(sample_path), "--family", "local_small"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "### TASK" in out
    assert "### END" in out


def test_cli_missing_spec_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    missing = tmp_path / "does_not_exist.json"
    rc = cli_main(["compile", str(missing), "--family", "openai_compat"])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err
