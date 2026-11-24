"""Multi-family matrix compiler for comparing prompt footprints across model families."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from promptweave.adapters import SUPPORTED_FAMILIES
from promptweave.compiler import CompiledPrompt, compile_prompt
from promptweave.spec import IntentSpec
from promptweave.templates import bind_variables

# Friendly aliases accepted in compile_matrix while canonicalizing to SUPPORTED_FAMILIES.
_FAMILY_ALIASES: dict[str, str] = {
    "anthropic": "claude",
    "llama_local": "local_small",
}


def _resolve_families(families: Sequence[str] | None) -> list[str]:
    if families is None:
        return list(SUPPORTED_FAMILIES)
    if len(families) == 0:
        raise ValueError("families must contain at least one model family.")

    resolved: list[str] = []
    seen: set[str] = set()
    for raw in families:
        name = raw.strip()
        canonical = _FAMILY_ALIASES.get(name, name)
        if canonical not in SUPPORTED_FAMILIES:
            supported = ", ".join(SUPPORTED_FAMILIES)
            raise ValueError(
                f"Unsupported model family '{raw}'. Supported families: {supported}"
            )
        if canonical not in seen:
            seen.add(canonical)
            resolved.append(canonical)
    return resolved


@dataclass(frozen=True)
class MatrixFamilyEntry:
    """Per-family compilation summary inside a :class:`MatrixReport`."""

    family: str
    prompt_id: str
    sha256: str
    estimated_tokens: int
    trimmed_blocks: tuple[str, ...] = ()
    compiled: CompiledPrompt | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "prompt_id": self.prompt_id,
            "sha256": self.sha256,
            "estimated_tokens": self.estimated_tokens,
            "trimmed_blocks": list(self.trimmed_blocks),
        }


@dataclass(frozen=True)
class MatrixReport:
    """Comparison report produced by :func:`compile_matrix`."""

    spec_name: str
    families: dict[str, MatrixFamilyEntry]
    min_tokens_family: str
    max_tokens_family: str
    variables_bound: dict[str, str] = field(default_factory=dict)
    max_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_name": self.spec_name,
            "families": {name: entry.to_dict() for name, entry in self.families.items()},
            "min_tokens_family": self.min_tokens_family,
            "max_tokens_family": self.max_tokens_family,
            "variables_bound": dict(self.variables_bound),
            "max_tokens": self.max_tokens,
        }


def compile_matrix(
    spec: IntentSpec,
    *,
    families: Sequence[str] | None = None,
    variables: Mapping[str, str] | None = None,
    max_tokens: int | None = None,
) -> MatrixReport:
    """Compile an IntentSpec across multiple model families and compare footprints.

    Parameters
    ----------
    spec:
        The :class:`IntentSpec` to compile.
    families:
        Optional subset of model families to compile. Defaults to all 4 supported
        families in :data:`SUPPORTED_FAMILIES`.
    variables:
        Optional template variables bound via :func:`bind_variables` prior to
        compilation (strict mode).
    max_tokens:
        Optional token budget passed to :func:`compile_prompt` for each family.
    """
    target_families = _resolve_families(families)
    bound_vars: dict[str, str] = {}
    effective_spec = spec
    if variables is not None:
        bound_vars = {str(k): str(v) for k, v in variables.items()}
        effective_spec = bind_variables(spec, bound_vars, strict=True)

    entries: dict[str, MatrixFamilyEntry] = {}
    for family in target_families:
        compiled = compile_prompt(effective_spec, family=family, max_tokens=max_tokens)
        entries[family] = MatrixFamilyEntry(
            family=family,
            prompt_id=compiled.prompt_id,
            sha256=compiled.sha256,
            estimated_tokens=compiled.estimated_tokens,
            trimmed_blocks=tuple(compiled.dropped_context_blocks),
            compiled=compiled,
        )

    min_family = min(target_families, key=lambda fam: entries[fam].estimated_tokens)
    max_family = max(target_families, key=lambda fam: entries[fam].estimated_tokens)

    return MatrixReport(
        spec_name=effective_spec.name,
        families=entries,
        min_tokens_family=min_family,
        max_tokens_family=max_family,
        variables_bound=bound_vars,
        max_tokens=max_tokens,
    )
