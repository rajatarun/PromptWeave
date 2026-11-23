"""Structured intent specification dataclasses for PromptWeave."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContextBlock:
    """A labeled block of context with a numeric priority (higher = kept first)."""

    label: str
    content: str
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "content": self.content,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextBlock:
        if not isinstance(data, dict):
            raise ValueError("ContextBlock must be a mapping.")
        label = str(data.get("label") or data.get("id") or data.get("title") or "context")
        content = str(data.get("content", ""))
        priority = int(data.get("priority", 0))
        return cls(label=label, content=content, priority=priority)


@dataclass(frozen=True)
class Example:
    """Few-shot input/output example."""

    input: str
    output: str

    def to_dict(self) -> dict[str, str]:
        return {"input": self.input, "output": self.output}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Example:
        if not isinstance(data, dict):
            raise ValueError("Example must be a mapping.")
        return cls(input=str(data.get("input", "")), output=str(data.get("output", "")))


def _normalize_constraints(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw if str(item).strip())
    if isinstance(raw, dict):
        items: list[str] = []
        for key in sorted(raw.keys()):
            val = raw[key]
            if isinstance(val, bool):
                if val:
                    items.append(str(key))
                else:
                    items.append(f"not {key}")
            else:
                items.append(f"{key}: {val}")
        return tuple(items)
    return (str(raw),)


@dataclass(frozen=True)
class IntentSpec:
    """Model-agnostic structured intent specification."""

    task: str
    name: str = "default"
    role: str | None = None
    audience: str | None = None
    tone: str | None = None
    constraints: tuple[str, ...] | list[str] = field(default_factory=tuple)
    output_schema: dict[str, Any] | str | None = None
    context_blocks: tuple[ContextBlock, ...] | list[ContextBlock] = field(default_factory=tuple)
    examples: tuple[Example, ...] | list[Example] = field(default_factory=tuple)
    tools: tuple[dict[str, Any], ...] | list[dict[str, Any]] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.task, str) or not self.task.strip():
            raise ValueError("IntentSpec.task must be a non-empty string.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("IntentSpec.name must be a non-empty string.")

        # Normalize mutable sequence inputs into deterministic tuples.
        object.__setattr__(self, "constraints", _normalize_constraints(self.constraints))

        norm_blocks: list[ContextBlock] = []
        for blk in self.context_blocks:
            if isinstance(blk, ContextBlock):
                norm_blocks.append(blk)
            elif isinstance(blk, dict):
                norm_blocks.append(ContextBlock.from_dict(blk))
            else:
                raise ValueError(f"Invalid context block: {blk!r}")
        object.__setattr__(self, "context_blocks", tuple(norm_blocks))

        norm_examples: list[Example] = []
        for ex in self.examples:
            if isinstance(ex, Example):
                norm_examples.append(ex)
            elif isinstance(ex, dict):
                norm_examples.append(Example.from_dict(ex))
            else:
                raise ValueError(f"Invalid example: {ex!r}")
        object.__setattr__(self, "examples", tuple(norm_examples))

        object.__setattr__(self, "tools", tuple(dict(t) for t in self.tools))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task": self.task,
            "role": self.role,
            "audience": self.audience,
            "tone": self.tone,
            "constraints": list(self.constraints),
            "output_schema": self.output_schema,
            "context_blocks": [b.to_dict() for b in self.context_blocks],
            "examples": [e.to_dict() for e in self.examples],
            "tools": list(self.tools),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentSpec:
        if not isinstance(data, dict):
            raise ValueError("IntentSpec payload must be a JSON object.")
        if "task" not in data:
            raise ValueError("IntentSpec requires a 'task' field.")

        output_schema = data.get("output_schema")
        if output_schema is None and "format" in data:
            output_schema = data["format"]

        return cls(
            name=str(data.get("name") or "default"),
            task=str(data["task"]),
            role=data.get("role"),
            audience=data.get("audience"),
            tone=data.get("tone"),
            constraints=_normalize_constraints(data.get("constraints")),
            output_schema=output_schema,
            context_blocks=[ContextBlock.from_dict(b) for b in (data.get("context_blocks") or [])],
            examples=[Example.from_dict(e) for e in (data.get("examples") or [])],
            tools=list(data.get("tools") or []),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> IntentSpec:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)
