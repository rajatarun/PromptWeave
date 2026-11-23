"""Strict {{variable}} template binding for PromptWeave IntentSpec."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from promptweave.spec import ContextBlock, IntentSpec

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.-]*)\s*\}\}")


class UnresolvedVariableError(ValueError):
    """Raised when strict variable binding encounters missing template placeholders."""

    def __init__(self, missing: list[str] | tuple[str, ...]) -> None:
        unique_missing = tuple(sorted(set(missing)))
        self.missing: tuple[str, ...] = unique_missing
        joined = ", ".join(unique_missing)
        super().__init__(f"Unresolved template variable(s): {joined}")


def _substitute_text(
    text: str,
    variables: Mapping[str, Any],
    missing: set[str],
) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in variables and variables[name] is not None:
            return str(variables[name])
        missing.add(name)
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, text)


def bind_variables(
    spec: IntentSpec,
    variables: Mapping[str, str],
    *,
    strict: bool = True,
) -> IntentSpec:
    """Substitute ``{{var_name}}`` placeholders across an IntentSpec without mutating it.

    Placeholders are bound across ``task``, ``role``, ``constraints``, and
    ``context_blocks`` content. When ``strict=True``, raises
    :class:`UnresolvedVariableError` listing all unresolved variable names.
    When ``strict=False``, unresolved placeholders are left untouched.
    """
    missing: set[str] = set()

    bound_task = _substitute_text(spec.task, variables, missing)
    bound_role = (
        _substitute_text(spec.role, variables, missing) if spec.role is not None else None
    )
    bound_constraints = tuple(
        _substitute_text(item, variables, missing) for item in spec.constraints
    )
    bound_blocks = tuple(
        ContextBlock(
            label=block.label,
            content=_substitute_text(block.content, variables, missing),
            priority=block.priority,
        )
        for block in spec.context_blocks
    )

    if strict and missing:
        raise UnresolvedVariableError(sorted(missing))

    return IntentSpec(
        name=spec.name,
        task=bound_task,
        role=bound_role,
        audience=spec.audience,
        tone=spec.tone,
        constraints=bound_constraints,
        output_schema=spec.output_schema,
        context_blocks=bound_blocks,
        examples=spec.examples,
        tools=spec.tools,
    )
