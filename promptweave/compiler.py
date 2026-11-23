"""Deterministic prompt compiler with token budgeting and SHA-256 fingerprinting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from promptweave.adapters import SUPPORTED_FAMILIES, render_for_family
from promptweave.fingerprint import compute_sha256, format_prompt_id
from promptweave.spec import ContextBlock, IntentSpec


def estimate_tokens(text: str) -> int:
    """Deterministic zero-dependency token estimator (~4 characters per token)."""
    if not text:
        return 0
    return (len(text) + 3) // 4


@dataclass(frozen=True)
class CompiledPrompt:
    """Output of compiling an IntentSpec for a target model family."""

    family: str
    prompt_id: str
    sha256: str
    system: str
    user: str
    messages: list[dict[str, str]]
    rendered: str
    estimated_tokens: int
    dropped_context_blocks: list[str] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "prompt_id": self.prompt_id,
            "sha256": self.sha256,
            "system": self.system,
            "user": self.user,
            "messages": list(self.messages),
            "rendered": self.rendered,
            "estimated_tokens": self.estimated_tokens,
            "dropped_context_blocks": list(self.dropped_context_blocks),
            "tools": list(self.tools),
        }


def compile_prompt(
    spec: IntentSpec,
    family: str = "openai_compat",
    max_tokens: int | None = None,
) -> CompiledPrompt:
    """Compile an IntentSpec into a model-family-optimized prompt with SHA-256 fingerprint.

    When ``max_tokens`` is set and the rendered prompt exceeds the budget, context blocks
    are trimmed in ascending order of ``priority`` (lowest priority dropped first; ties
    drop later blocks first) while preserving relative order among retained blocks.
    """
    if family not in SUPPORTED_FAMILIES:
        supported = ", ".join(SUPPORTED_FAMILIES)
        raise ValueError(f"Unsupported model family '{family}'. Supported families: {supported}")
    if max_tokens is not None and max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer.")

    active_blocks: list[ContextBlock] = list(spec.context_blocks)
    dropped_labels: list[str] = []

    parts = render_for_family(spec, family, active_blocks)
    estimated = estimate_tokens(parts.rendered)

    if max_tokens is not None:
        while active_blocks and estimated > max_tokens:
            # Drop lowest priority first; on ties drop the later block first.
            drop_idx = min(
                range(len(active_blocks)),
                key=lambda i: (active_blocks[i].priority, -i),
            )
            dropped = active_blocks.pop(drop_idx)
            dropped_labels.append(dropped.label)
            parts = render_for_family(spec, family, active_blocks)
            estimated = estimate_tokens(parts.rendered)

    fingerprint_payload: dict[str, Any] = {
        "family": family,
        "name": spec.name,
        "messages": parts.messages,
        "rendered": parts.rendered,
        "tools": list(spec.tools),
        "dropped_context_blocks": dropped_labels,
    }
    digest = compute_sha256(fingerprint_payload)
    prompt_id = format_prompt_id(spec.name, digest)

    return CompiledPrompt(
        family=family,
        prompt_id=prompt_id,
        sha256=digest,
        system=parts.system,
        user=parts.user,
        messages=parts.messages,
        rendered=parts.rendered,
        estimated_tokens=estimated,
        dropped_context_blocks=dropped_labels,
        tools=list(spec.tools),
    )
