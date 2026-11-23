"""PromptWeave — deterministic multi-family prompt compiler with SHA-256 fingerprinting."""

from promptweave.adapters import SUPPORTED_FAMILIES
from promptweave.compiler import CompiledPrompt, compile_prompt, estimate_tokens
from promptweave.diff import PromptDiff, diff_compiled
from promptweave.fingerprint import compute_sha256, format_prompt_id
from promptweave.registry import PROMPT_ARTIFACT_SCHEMA, PromptRegistry
from promptweave.spec import ContextBlock, Example, IntentSpec
from promptweave.templates import UnresolvedVariableError, bind_variables

__version__ = "0.2.0"

__all__ = [
    "CompiledPrompt",
    "ContextBlock",
    "Example",
    "IntentSpec",
    "PROMPT_ARTIFACT_SCHEMA",
    "PromptDiff",
    "PromptRegistry",
    "SUPPORTED_FAMILIES",
    "UnresolvedVariableError",
    "__version__",
    "bind_variables",
    "compile_prompt",
    "compute_sha256",
    "diff_compiled",
    "estimate_tokens",
    "format_prompt_id",
]
