"""Structural and token-delta diffing for compiled PromptWeave prompts."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

from promptweave.compiler import CompiledPrompt


def _unified_diff(before_text: str, after_text: str, *, label: str) -> str:
    if before_text == after_text:
        return ""
    lines = list(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=f"before/{label}",
            tofile=f"after/{label}",
            lineterm="",
        )
    )
    return "\n".join(lines)


@dataclass(frozen=True)
class PromptDiff:
    """Structured diff between two CompiledPrompt artifacts."""

    changed: bool
    sha256_changed: bool
    token_delta: int
    family_changed: bool
    unified_system_diff: str
    unified_user_diff: str
    before_prompt_id: str = ""
    after_prompt_id: str = ""
    before_tokens: int = 0
    after_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "sha256_changed": self.sha256_changed,
            "token_delta": self.token_delta,
            "family_changed": self.family_changed,
            "unified_system_diff": self.unified_system_diff,
            "unified_user_diff": self.unified_user_diff,
            "before_prompt_id": self.before_prompt_id,
            "after_prompt_id": self.after_prompt_id,
            "before_tokens": self.before_tokens,
            "after_tokens": self.after_tokens,
        }


def diff_compiled(before: CompiledPrompt, after: CompiledPrompt) -> PromptDiff:
    """Compute structural, SHA-256, family, and token diffs between two compiled prompts."""
    sha256_changed = before.sha256 != after.sha256
    family_changed = before.family != after.family
    token_delta = after.estimated_tokens - before.estimated_tokens
    unified_system_diff = _unified_diff(before.system, after.system, label="system")
    unified_user_diff = _unified_diff(before.user, after.user, label="user")
    changed = (
        sha256_changed
        or family_changed
        or bool(unified_system_diff)
        or bool(unified_user_diff)
        or (before.rendered != after.rendered)
    )
    return PromptDiff(
        changed=changed,
        sha256_changed=sha256_changed,
        token_delta=token_delta,
        family_changed=family_changed,
        unified_system_diff=unified_system_diff,
        unified_user_diff=unified_user_diff,
        before_prompt_id=before.prompt_id,
        after_prompt_id=after.prompt_id,
        before_tokens=before.estimated_tokens,
        after_tokens=after.estimated_tokens,
    )
