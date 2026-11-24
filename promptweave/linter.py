"""Static prompt policy linter and token budget validator for PromptWeave."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from promptweave.compiler import compile_prompt, estimate_tokens
from promptweave.spec import IntentSpec
from promptweave.templates import _PLACEHOLDER_RE

_QUOTED_SEGMENT_RE = re.compile(r'"[^"\n]*"|`[^`\n]*`')

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore-previous-instructions",
        re.compile(
            r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "disregard-previous-instructions",
        re.compile(
            r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "forget-previous-instructions",
        re.compile(
            r"\bforget\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "override-system-prompt",
        re.compile(
            r"\boverride\s+(?:the\s+)?(?:system|previous)\s+(?:prompt|instructions?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak-mode",
        re.compile(
            r"\byou\s+are\s+now\s+(?:in\s+)?(?:developer|dan|unrestricted|jailbreak)\s+mode\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal-system-prompt",
        re.compile(r"\breveal\s+(?:the\s+|your\s+)?system\s+prompt\b", re.IGNORECASE),
    ),
    (
        "raw-system-tag",
        re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    ),
    (
        "raw-system-delimiter",
        re.compile(r"(?:^|\n)\s*###\s*SYSTEM\b", re.IGNORECASE),
    ),
)


@dataclass(frozen=True)
class LintIssue:
    """A single policy, safety, or token-budget issue found in an IntentSpec."""

    severity: str
    code: str
    block_id: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "block_id": self.block_id,
            "message": self.message,
        }


@dataclass(frozen=True)
class LintReport:
    """Structured lint report returned by :func:`lint_prompt_spec`."""

    ok: bool
    error_count: int
    warning_count: int
    estimated_tokens: int
    max_tokens: int | None
    issues: list[LintIssue]
    block_tokens: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "estimated_tokens": self.estimated_tokens,
            "max_tokens": self.max_tokens,
            "block_tokens": dict(self.block_tokens),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _scan_text_for_injection_risks(
    text: str,
    *,
    location: str,
    block_id: str | None,
    issues: list[LintIssue],
) -> None:
    """Append INJECTION_RISK_PATTERN warnings for unresolved placeholders or injection markers."""
    if not text:
        return

    placeholders = sorted(set(_PLACEHOLDER_RE.findall(text)))
    if placeholders:
        formatted = ", ".join(f"{{{{{name}}}}}" for name in placeholders)
        issues.append(
            LintIssue(
                severity="warning",
                code="INJECTION_RISK_PATTERN",
                block_id=block_id,
                message=(
                    f"Unresolved template placeholder(s) {formatted} in {location}; "
                    "bind variables before deployment."
                ),
            )
        )

    unquoted = _QUOTED_SEGMENT_RE.sub(" ", text)
    for pattern_name, regex in _INJECTION_PATTERNS:
        match = regex.search(unquoted)
        if match is not None:
            issues.append(
                LintIssue(
                    severity="warning",
                    code="INJECTION_RISK_PATTERN",
                    block_id=block_id,
                    message=(
                        f"Potential prompt-injection marker ({pattern_name}: "
                        f"'{match.group(0).strip()}') detected in {location}."
                    ),
                )
            )


def lint_prompt_spec(
    spec: IntentSpec,
    *,
    max_tokens: int | None = None,
    require_system_goal: bool = True,
) -> LintReport:
    """Statically lint an :class:`IntentSpec` for policy, safety, and token budget issues.

    Checks performed:
    - ``MISSING_SYSTEM_GOAL`` (error): Missing/empty system role or constraint instructions
      when ``require_system_goal=True``.
    - ``DUPLICATE_BLOCK_ID`` (error): Duplicate ``ContextBlock.label`` identifiers.
    - ``INJECTION_RISK_PATTERN`` (warning): Unresolved ``{{variable}}`` placeholders or
      unquoted prompt-injection markers (e.g. ``ignore previous instructions``) in static
      prompt sections and context blocks.
    - ``TOKEN_BUDGET_EXCEEDED`` (error): Estimated total token footprint exceeding
      ``max_tokens``, including a per-block token breakdown.
    """
    if max_tokens is not None and max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer.")

    issues: list[LintIssue] = []

    # 1. System goal / instructions guardrail
    has_role = bool(spec.role and spec.role.strip())
    has_constraints = any(item.strip() for item in spec.constraints)
    if require_system_goal and not (has_role or has_constraints):
        issues.append(
            LintIssue(
                severity="error",
                code="MISSING_SYSTEM_GOAL",
                block_id=None,
                message=(
                    "Missing system goal or instructions: provide a non-empty 'role' "
                    "or at least one 'constraints' entry."
                ),
            )
        )

    # 2. Duplicate context block IDs
    label_counts: Counter[str] = Counter()
    for block in spec.context_blocks:
        label_counts[block.label] += 1
        if label_counts[block.label] > 1:
            issues.append(
                LintIssue(
                    severity="error",
                    code="DUPLICATE_BLOCK_ID",
                    block_id=block.label,
                    message=(
                        f"Duplicate context block ID '{block.label}' "
                        f"(occurrence #{label_counts[block.label]})."
                    ),
                )
            )

    # 3. Unresolved placeholders and raw injection markers
    _scan_text_for_injection_risks(
        spec.task,
        location="task",
        block_id=None,
        issues=issues,
    )
    if spec.role is not None:
        _scan_text_for_injection_risks(
            spec.role,
            location="role",
            block_id=None,
            issues=issues,
        )
    for idx, constraint in enumerate(spec.constraints):
        _scan_text_for_injection_risks(
            constraint,
            location=f"constraints[{idx}]",
            block_id=None,
            issues=issues,
        )
    for block in spec.context_blocks:
        _scan_text_for_injection_risks(
            block.content,
            location=f"context_block '{block.label}'",
            block_id=block.label,
            issues=issues,
        )
    for idx, example in enumerate(spec.examples):
        _scan_text_for_injection_risks(
            example.input,
            location=f"examples[{idx}].input",
            block_id=None,
            issues=issues,
        )
        _scan_text_for_injection_risks(
            example.output,
            location=f"examples[{idx}].output",
            block_id=None,
            issues=issues,
        )

    # 4. Token footprint & per-block breakdown
    compiled = compile_prompt(spec, family="openai_compat", max_tokens=None)
    estimated_tokens = compiled.estimated_tokens

    block_tokens: dict[str, int] = {}
    breakdown_parts: list[str] = []
    for idx, block in enumerate(spec.context_blocks):
        tok = estimate_tokens(f"[{block.label}] {block.content}")
        block_tokens[block.label] = block_tokens.get(block.label, 0) + tok
        label_part = (
            f"{block.label}#{idx + 1}={tok}"
            if label_counts[block.label] > 1
            else f"{block.label}={tok}"
        )
        breakdown_parts.append(label_part)

    if max_tokens is not None and estimated_tokens > max_tokens:
        breakdown = ", ".join(breakdown_parts) if breakdown_parts else "none (base prompt only)"
        issues.append(
            LintIssue(
                severity="error",
                code="TOKEN_BUDGET_EXCEEDED",
                block_id=None,
                message=(
                    f"Estimated token footprint ({estimated_tokens}) exceeds max_tokens "
                    f"({max_tokens}). Per-block token breakdown: {breakdown}."
                ),
            )
        )

    error_count = sum(1 for item in issues if item.severity == "error")
    warning_count = sum(1 for item in issues if item.severity == "warning")

    return LintReport(
        ok=error_count == 0,
        error_count=error_count,
        warning_count=warning_count,
        estimated_tokens=estimated_tokens,
        max_tokens=max_tokens,
        issues=issues,
        block_tokens=block_tokens,
    )
