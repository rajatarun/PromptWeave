"""Model-family rendering adapters for PromptWeave."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from promptweave.spec import ContextBlock, IntentSpec

SUPPORTED_FAMILIES: tuple[str, ...] = (
    "local_small",
    "claude",
    "gemini",
    "openai_compat",
)


@dataclass(frozen=True)
class RenderedPromptParts:
    """Intermediate rendered prompt sections returned by a family adapter."""

    system: str
    user: str
    messages: list[dict[str, str]]
    rendered: str


def _format_output_schema(schema: dict[str, Any] | str | None) -> str:
    if schema is None:
        return ""
    if isinstance(schema, str):
        return schema.strip()
    return json.dumps(schema, sort_keys=True, indent=2)


def _format_tools(tools: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    if not tools:
        return ""
    return json.dumps(list(tools), sort_keys=True, indent=2)


def _render_local_small(spec: IntentSpec, blocks: list[ContextBlock]) -> RenderedPromptParts:
    """Compact, strict-delimiter layout optimized for 3B–8B local models."""
    sys_parts: list[str] = []
    if spec.role:
        sys_parts.append(f"### ROLE\n{spec.role}")
    meta: list[str] = []
    if spec.audience:
        meta.append(f"Audience: {spec.audience}")
    if spec.tone:
        meta.append(f"Tone: {spec.tone}")
    if meta:
        sys_parts.append("### STYLE\n" + "\n".join(meta))
    if spec.constraints:
        rules = "\n".join(f"- {c}" for c in spec.constraints)
        sys_parts.append(f"### RULES\n{rules}")
    if spec.tools:
        sys_parts.append(f"### TOOLS\n{_format_tools(spec.tools)}")
    if spec.output_schema is not None:
        sys_parts.append(f"### OUTPUT_FORMAT\n{_format_output_schema(spec.output_schema)}")
    system_text = "\n\n".join(sys_parts)

    user_parts: list[str] = []
    if blocks:
        ctx_lines = [f"[{b.label}] {b.content}" for b in blocks]
        user_parts.append("### CONTEXT\n" + "\n".join(ctx_lines))
    if spec.examples:
        ex_lines = [f"IN: {e.input}\nOUT: {e.output}" for e in spec.examples]
        user_parts.append("### EXAMPLES\n" + "\n---\n".join(ex_lines))
    user_parts.append(f"### TASK\n{spec.task}\n### END")
    user_text = "\n\n".join(user_parts)

    messages: list[dict[str, str]] = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})

    rendered = f"{system_text}\n\n{user_text}".strip() if system_text else user_text
    return RenderedPromptParts(
        system=system_text,
        user=user_text,
        messages=messages,
        rendered=rendered,
    )


def _render_claude(spec: IntentSpec, blocks: list[ContextBlock]) -> RenderedPromptParts:
    """XML-tagged structured sections idiomatic for Claude models."""
    sys_parts: list[str] = []
    if spec.role:
        sys_parts.append(f"<role>\n{spec.role}\n</role>")
    if spec.audience:
        sys_parts.append(f"<audience>{spec.audience}</audience>")
    if spec.tone:
        sys_parts.append(f"<tone>{spec.tone}</tone>")
    if spec.constraints:
        items = "\n".join(f"  <constraint>{c}</constraint>" for c in spec.constraints)
        sys_parts.append(f"<constraints>\n{items}\n</constraints>")
    if spec.tools:
        sys_parts.append(f"<tools>\n{_format_tools(spec.tools)}\n</tools>")
    if spec.output_schema is not None:
        sys_parts.append(
            f"<output_schema>\n{_format_output_schema(spec.output_schema)}\n</output_schema>"
        )
    system_text = "\n\n".join(sys_parts)

    user_parts: list[str] = []
    if blocks:
        ctx_xml = "\n".join(
            f'  <block label="{b.label}" priority="{b.priority}">\n{b.content}\n  </block>'
            for b in blocks
        )
        user_parts.append(f"<context>\n{ctx_xml}\n</context>")
    if spec.examples:
        ex_xml = "\n".join(
            f"  <example>\n    <input>{e.input}</input>\n"
            f"    <output>{e.output}</output>\n  </example>"
            for e in spec.examples
        )
        user_parts.append(f"<examples>\n{ex_xml}\n</examples>")
    user_parts.append(f"<task>\n{spec.task}\n</task>")
    user_text = "\n\n".join(user_parts)

    messages: list[dict[str, str]] = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})

    rendered = f"{system_text}\n\n{user_text}".strip() if system_text else user_text
    return RenderedPromptParts(
        system=system_text,
        user=user_text,
        messages=messages,
        rendered=rendered,
    )


def _render_gemini(spec: IntentSpec, blocks: list[ContextBlock]) -> RenderedPromptParts:
    """Structured Markdown sections optimized for Gemini models."""
    sys_parts: list[str] = []
    if spec.role:
        sys_parts.append(f"## Role\n{spec.role}")
    if spec.audience:
        sys_parts.append(f"## Audience\n{spec.audience}")
    if spec.tone:
        sys_parts.append(f"## Tone\n{spec.tone}")
    if spec.constraints:
        bullets = "\n".join(f"* {c}" for c in spec.constraints)
        sys_parts.append(f"## Constraints\n{bullets}")
    if spec.tools:
        sys_parts.append(f"## Tools\n```json\n{_format_tools(spec.tools)}\n```")
    if spec.output_schema is not None:
        schema_str = _format_output_schema(spec.output_schema)
        if isinstance(spec.output_schema, dict):
            sys_parts.append(f"## Output Schema\n```json\n{schema_str}\n```")
        else:
            sys_parts.append(f"## Output Format\n{schema_str}")
    system_text = "\n\n".join(sys_parts)

    user_parts: list[str] = []
    if blocks:
        ctx_md = "\n\n".join(f"### {b.label}\n{b.content}" for b in blocks)
        user_parts.append(f"## Context\n\n{ctx_md}")
    if spec.examples:
        ex_md = "\n\n".join(
            f"**Input:** {e.input}\n\n**Output:** {e.output}" for e in spec.examples
        )
        user_parts.append(f"## Examples\n\n{ex_md}")
    user_parts.append(f"## Task\n{spec.task}")
    user_text = "\n\n".join(user_parts)

    messages: list[dict[str, str]] = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})

    rendered = f"{system_text}\n\n{user_text}".strip() if system_text else user_text
    return RenderedPromptParts(
        system=system_text,
        user=user_text,
        messages=messages,
        rendered=rendered,
    )


def _render_openai_compat(spec: IntentSpec, blocks: list[ContextBlock]) -> RenderedPromptParts:
    """Clean system/user message split for OpenAI-compatible chat endpoints."""
    sys_lines: list[str] = []
    if spec.role:
        sys_lines.append(f"Role: {spec.role}")
    if spec.audience:
        sys_lines.append(f"Audience: {spec.audience}")
    if spec.tone:
        sys_lines.append(f"Tone: {spec.tone}")
    if spec.constraints:
        sys_lines.append("Constraints:")
        for c in spec.constraints:
            sys_lines.append(f"- {c}")
    if spec.tools:
        sys_lines.append(f"Available Tools:\n{_format_tools(spec.tools)}")
    if spec.output_schema is not None:
        sys_lines.append(f"Output Schema:\n{_format_output_schema(spec.output_schema)}")
    system_text = "\n".join(sys_lines)

    user_sections: list[str] = []
    if blocks:
        ctx_lines = [f"[{b.label}]\n{b.content}" for b in blocks]
        user_sections.append("Context:\n" + "\n\n".join(ctx_lines))
    if spec.examples:
        ex_lines = [f"Input: {e.input}\nOutput: {e.output}" for e in spec.examples]
        user_sections.append("Examples:\n" + "\n\n".join(ex_lines))
    user_sections.append(f"Task:\n{spec.task}")
    user_text = "\n\n".join(user_sections)

    messages: list[dict[str, str]] = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})

    rendered = (
        f"[system]\n{system_text}\n\n[user]\n{user_text}" if system_text else f"[user]\n{user_text}"
    )
    return RenderedPromptParts(
        system=system_text,
        user=user_text,
        messages=messages,
        rendered=rendered,
    )


_ADAPTERS = {
    "local_small": _render_local_small,
    "claude": _render_claude,
    "gemini": _render_gemini,
    "openai_compat": _render_openai_compat,
}


def render_for_family(
    spec: IntentSpec,
    family: str,
    context_blocks: list[ContextBlock] | None = None,
) -> RenderedPromptParts:
    """Render an IntentSpec using the specified model-family adapter."""
    adapter = _ADAPTERS.get(family)
    if adapter is None:
        supported = ", ".join(SUPPORTED_FAMILIES)
        raise ValueError(f"Unsupported model family '{family}'. Supported families: {supported}")
    blocks = list(spec.context_blocks) if context_blocks is None else list(context_blocks)
    return adapter(spec, blocks)
